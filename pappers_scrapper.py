import random
import time
from typing import List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from nodes import Person, Address, Director

# XPath for the "next page" button — update if Pappers changes its markup
_NEXT_PAGE_XPATH = "//a[contains(@class,'pagination-image-right') and not(contains(@class,'disabled'))]"


class CaptchaError(Exception):
    pass


def _random_wait(min_s: float = 1.5, max_s: float = 4.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _collect_page_links(driver) -> list[str | None]:
    result_div = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "container-resultat"))
    )
    return [div.find_element(By.TAG_NAME, "a").get_attribute("href") for div in result_div]


def _parse_director_href(href: str) -> tuple[str, str, str]:
    """Returns (first_name, last_name, birth_date) parsed from a /dirigeant/... href."""
    slug = href.rstrip("/").split("/")[-1]  # e.g. "bernard_bounias_1966-02"
    parts = slug.split("_")
    if parts[-1][0].isdigit():
        year, month = parts[-1].split("-")
        birth_date = f"{month}/{year}"
        name_parts = parts[:-1]
    else:
        birth_date = ""
        name_parts = parts
    first_name = name_parts[0].capitalize()
    last_name = " ".join(p.capitalize() for p in name_parts[1:])
    return first_name, last_name, birth_date


PersonKey = tuple[str, str, str | None]


def _extract_directors(driver, person_registry: dict[PersonKey, Person]) -> list[Director]:
    directors = []
    for item in driver.find_elements(By.XPATH, "//li[contains(@class,'dirigeant')]"):
        anchor = item.find_element(By.XPATH, ".//div[@class='nom']//a")
        href = anchor.get_attribute("href")
        # Skip entries that are legal entities (link to /entreprise/...) rather than natural persons
        #TODO : Fix pitfall that skips directors with this href : "https://www.pappers.fr/recherche-dirigeants?q=bernard%20bounias"
        if href is None or "/dirigeant/" not in href:
            continue
        first_name, last_name, birth_date = _parse_director_href(href)
        role = item.find_element(By.XPATH, ".//span[@class='qualite']").text.strip()
        since_text = item.find_element(By.XPATH, ".//span[@class='date']").text.strip()
        key: PersonKey = (first_name, last_name, birth_date or None)
        if key not in person_registry:
            person_registry[key] = Person(first_name, last_name, birth_date=key[2])
        directors.append(Director(person_registry[key], role, since_text))
    return directors


def _has_next_page(driver) -> bool:
    try:
        driver.find_element(By.XPATH, _NEXT_PAGE_XPATH)
        return True
    except NoSuchElementException:
        return False

class PapperResultSociety:
    def __init__(self, name: str, address: Address, siret: str, creation_date: str, link: str, directors: list[Director]):
        self.name = name
        self.address = address
        self.siret = siret
        self.creation_date = creation_date
        self.link = link
        self.directors = directors
    def __str__(self):
        return f"PapperResultSociety(name={self.name}, address={self.address}, siret={self.siret}, creation_date={self.creation_date}, link={self.link})"

def lookup(first_name: str, last_name: str) -> List[PapperResultSociety]:
    """
    Lookup a person on Pappers and return a list of PapperResultSociety objects.
    """
    results: list[PapperResultSociety] = []
    person_registry: dict[PersonKey, Person] = {}
    URL=f"https://www.pappers.fr/recherche?q={first_name}+{last_name}"
    driver = webdriver.Chrome()
    driver.get(URL)
    _random_wait()
    links: list[str | None] = []
    while True:
        try:
            links.extend(_collect_page_links(driver))
        except TimeoutException:
            driver.quit()
            raise CaptchaError("Search results did not load — Pappers may have triggered a CAPTCHA")

        if not _has_next_page(driver):
            break

        _random_wait()
        driver.find_element(By.XPATH, _NEXT_PAGE_XPATH).click()
        _random_wait()
    for result_link in links:
        if result_link is None:
            continue
        _random_wait()
        driver.get(result_link)
        _random_wait()
        try:
            siret = driver.find_element(By.XPATH, "//th[contains(text(),'SIRET')]/following-sibling::td").text
            name = driver.find_element(By.XPATH, "//h1").text
            address_text = driver.find_element(By.XPATH, "//th[contains(text(),'Adresse')]/following-sibling::td").text
            creation_date = driver.find_element(By.XPATH, "//th[contains(text(),'ation :')]/following-sibling::td").text
        except Exception:
            driver.quit()
            raise CaptchaError(f"Expected elements missing on {result_link} — Pappers may have triggered a CAPTCHA")

        #Adress is in the pattern "Number Street, Postal Code City"
        address_parts = address_text.split(", ")
        street = address_parts[0]
        postal_code_city = address_parts[1].split(" ")
        postal_code = postal_code_city[0]
        city = " ".join(postal_code_city[1:])
        address = Address(street, city, postal_code)
        directors = _extract_directors(driver, person_registry)
        result = PapperResultSociety(name, address, siret, creation_date, result_link, directors)
        results.append(result)
    driver.quit()

    return results