import argparse
import sys

from pappers_scrapper import lookup, CaptchaError
import holehe_scraper
from graph import GossipGraph


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gossipsea",
        description="OSINT pipeline for gathering information on individuals.",
    )
    parser.add_argument("--first-name", metavar="NAME", help="Target's first name")
    parser.add_argument("--last-name", metavar="NAME", help="Target's last name")
    parser.add_argument("--email", metavar="EMAIL", help="Target's email address")
    parser.add_argument("--phone", metavar="PHONE", help="Target's phone number (not yet implemented)")
    parser.add_argument("--username", metavar="USERNAME", help="Target's username (not yet implemented)")
    parser.add_argument("--domain", metavar="DOMAIN", help="Target domain (not yet implemented)")
    parser.add_argument("--ip", metavar="IP", help="Target IP address (not yet implemented)")
    parser.add_argument("-o", "--output", metavar="FILE", default="output.cypher",
                        help="Path for the exported Cypher file (default: output.cypher)")
    parser.add_argument("--html-output", metavar="FILE", default="output.html",
                        help="Path for the interactive HTML graph (default: output.html)")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    graph = GossipGraph()
    ran_any = False

    if args.first_name and args.last_name:
        ran_any = True
        graph.add_original_person(args.first_name, args.last_name)
        print(f"Searching Pappers for {args.first_name} {args.last_name}...")
        try:
            results = lookup(args.first_name, args.last_name)
        except CaptchaError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Found {len(results)} company/companies.")
        graph.load_pappers(results)

    if args.email:
        ran_any = True
        graph.add_original_email(args.email)
        print(f"Searching holehe for {args.email}...")
        results = holehe_scraper.lookup(args.email)
        print(f"Found {len(results)} registered account(s).")
        graph.load_holehe(args.email, results)

    for flag, name in [("--phone", args.phone),
                       ("--username", args.username), ("--domain", args.domain), ("--ip", args.ip)]:
        if name:
            print(f"Warning: {flag} is not yet implemented, skipping.", file=sys.stderr)

    if not ran_any:
        parser.print_help()
        sys.exit(0)

    graph.export_cypher(args.output)
    print(f"Graph exported to {args.output}")

    graph.export_html(args.html_output)
    print(f"Interactive graph written to {args.html_output}")


if __name__ == "__main__":
    main()
