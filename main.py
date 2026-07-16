import argparse
import sys

from recherche_entreprises_scraper import lookup, RechercheEntreprisesError
import extrapolation
import holehe_scraper
import maigret_scraper
import phoneinfoga_scraper
import sherlock_scraper
from graph import GossipGraph


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gossipsea",
        description="OSINT pipeline for gathering information on individuals.",
    )
    parser.add_argument("--first-name", metavar="NAME", help="Target's first name")
    parser.add_argument("--last-name", metavar="NAME", help="Target's last name")
    parser.add_argument("--dob", metavar="DATE", help="Target's date of birth (e.g. 1990-05-14); recorded on the original Person node")
    parser.add_argument("--email", metavar="EMAIL", nargs="+", help="Target's email address(es)")
    parser.add_argument("--email-file", metavar="FILE", help="Path to a file with one email address per line")
    parser.add_argument("--phone", metavar="PHONE", help="Target's phone number")
    parser.add_argument("--username", metavar="USERNAME", nargs="+", help="Target's username(s)")
    parser.add_argument("--username-file", metavar="FILE", help="Path to a file with one username per line")
    parser.add_argument("-o", "--output", metavar="FILE", default="output.cypher",
                        help="Path for the exported Cypher file (default: output.cypher)")
    parser.add_argument("--html-output", metavar="FILE", default="output.html",
                        help="Path for the interactive HTML graph (default: output.html)")
    return parser


def _collect_values(values: list[str] | None, file_path: str | None) -> list[str]:
    result = list(values) if values else []
    if file_path:
        with open(file_path, encoding="utf-8") as f:
            result.extend(line.strip() for line in f if line.strip())
    return result


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    graph = GossipGraph()
    ran_any = False

    if args.first_name and args.last_name:
        ran_any = True
        graph.add_original_person(args.first_name, args.last_name, birth_date=args.dob)
        print(f"Searching Recherche d'entreprises for {args.first_name} {args.last_name}...")
        try:
            results = lookup(args.first_name, args.last_name)
        except RechercheEntreprisesError as e:
            print(f"Error: {e}", file=sys.stderr)
            results = []
        print(f"Found {len(results)} company/companies.")
        graph.load_recherche_entreprises(results)
    elif args.dob:
        print("Warning: --dob requires --first-name and --last-name, skipping.", file=sys.stderr)

    emails = _collect_values(args.email, args.email_file)
    if emails:
        ran_any = True
        for email in emails:
            graph.add_original_email(email)
            print(f"Searching holehe for {email}...")
            results = holehe_scraper.lookup(email)
            print(f"Found {len(results)} registered account(s).")
            graph.load_holehe(email, results)

    if args.phone:
        ran_any = True
        graph.add_original_phone(args.phone)
        print(f"Searching Phoneinfoga for {args.phone}...")
        try:
            results = phoneinfoga_scraper.lookup(args.phone)
        except phoneinfoga_scraper.PhoneinfogaError as e:
            print(f"Error: {e}", file=sys.stderr)
            results = []
        graph.load_phoneinfoga(args.phone, results)

    provided_usernames = _collect_values(args.username, args.username_file)
    extrapolated_usernames = (
        extrapolation.generate_usernames(args.first_name, args.last_name, args.dob)
        if args.first_name and args.last_name else []
    )
    all_usernames = provided_usernames + [u for u in extrapolated_usernames if u not in provided_usernames]

    if all_usernames:
        ran_any = True
        for username in provided_usernames:
            graph.add_original_username(username)
        for username in extrapolated_usernames:
            if username not in provided_usernames:
                graph.add_extrapolated_username(username)

        for username in all_usernames:
            print(f"Searching Sherlock for {username}...")
            try:
                results = sherlock_scraper.lookup(username)
            except sherlock_scraper.SherlockError as e:
                print(f"Error: {e}", file=sys.stderr)
                results = []
            print(f"Found {len(results)} account(s).")
            graph.load_sherlock(username, results)

            print(f"Searching Maigret for {username}...")
            try:
                results = maigret_scraper.lookup(username)
            except maigret_scraper.MaigretError as e:
                print(f"Error: {e}", file=sys.stderr)
                results = []
            print(f"Found {len(results)} account(s).")
            graph.load_maigret(username, results)

            for email in extrapolation.generate_emails(username):
                graph.add_extrapolated_email(username, email)
                print(f"Searching holehe for extrapolated email {email}...")
                results = holehe_scraper.lookup(email)
                graph.load_holehe(email, results)

    if not ran_any:
        parser.print_help()
        sys.exit(0)

    graph.export_cypher(args.output)
    print(f"Graph exported to {args.output}")

    graph.export_html(args.html_output)
    print(f"Interactive graph written to {args.html_output}")


if __name__ == "__main__":
    main()
