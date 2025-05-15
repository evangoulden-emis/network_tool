from argparse import ArgumentParser, Namespace

import requests
from dns import resolver
from rich.console import Console
from rich.table import Table
import ipaddress

BGPVIEW = "https://api.bgpview.io"


def main(args: Namespace):
    if args.fqdn is None and args.nameserver is None and args.subnet is None and args.target_host is None \
            and args.bgp is None:
        print("No arguments provided. Use --help for more information.")
        return
    if args.fqdn and args.nameserver is not None:
        fqdn(args.fqdn[0], args.nameserver[0])
    elif args.fqdn:
        fqdn(args.fqdn[0])
    elif args.bgp:
        bgp(args.bgp)


def bgp(bgp: Namespace):
    asn = None
    console = Console()
    try:
        if bgp.isdigit():
            '''Treat BGP as an ASN'''
            asn = int(str(bgp))
            console.print(f"[bold]BGP ASN:[/bold] {asn}")
            # Perform BGP lookup using the ASN
            try:
                response = requests.get(f"{BGPVIEW}/asn/{asn}/prefixes")
                if response.status_code == 200:
                    data = response.json()
                    # Extract relevant information
                    asn_info = data.get('data', {})
                    prefixes = asn_info.get('ipv4_prefixes', [])
                    table = Table(title=f"ASN {asn} Information", show_lines=True)
                    table.add_column("Name", style="cyan")
                    table.add_column("Prefix", style="green")
                    table.add_column("CIDR", style="magenta")
                    table.add_column("Status", style="yellow")
                    for prefix in prefixes:
                        table.add_row(
                            prefix['name'],
                            prefix['prefix'],
                            str(prefix['cidr']),
                            "✓"
                        )
                    console.print(table, new_line_start=True)
            except requests.exceptions.RequestException as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                return
        elif get_ip_or_none(str(bgp)):
            prefix = ipaddress.ip_network(str(bgp))
            try:
                response = requests.get(f"{BGPVIEW}/prefix/{prefix}")
                if response.status_code == 200:
                    data = response.json()
                    # Extract relevant information
                    prefix_info = data.get('data', {})
                    prefixes = prefix_info.get('ipv4_prefixes', [])
                    prefix_table = Table(title=f"Prefix {prefix} Information", show_lines=True)
                    prefix_table.add_column("Name", style="cyan")
                    prefix_table.add_column("Prefix", style="green")
                    prefix_table.add_column("IP", style="blue")
                    prefix_table.add_column("Description", style="magenta")
                    prefix_table.add_column("ASN Count", style="blue_violet")
                    prefix_table.add_column("Status", style="yellow")
                    prefix_table.add_row(
                        prefix_info['name'],
                        prefix_info['prefix'],
                        prefix_info['ip'],
                        prefix_info['description_short'] if prefix_info['description_short'] else "UNKNOWN",
                        str(len(prefix_info['asns'])),
                        "✓"
                    )
                    asn_count = len(prefix_info['asns'])
                    asn_table = Table(title=f"ASN Information for {prefix}", show_lines=True)
                    asn_table.add_column("ASN", style="cyan")
                    asn_table.add_column("Name", style="green")
                    asn_table.add_column("Description", style="magenta")
                    asn_table.add_column("Country Code", style="yellow")
                    asn_table.add_column("Upstream ASNs", style="blue")
                    asn_table.add_column("Upstream ASN Names", style="cyan")
                    for asn in prefix_info['asns']:
                        for upstream_asn in asn['prefix_upstreams']:
                            asn_table.add_row(
                                str(asn['asn']),
                                asn['name'],
                                asn['description'],
                                asn['country_code'],
                                str(upstream_asn['asn']),
                                upstream_asn['name']
                            )

                    console.print(prefix_table, new_line_start=True)
                    console.print(asn_table, new_line_start=True)
            except requests.exceptions.RequestException as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                return

        else:
            print(f"Error: Unable to retrieve BGP information for ASN {asn}.")
    except ValueError:
        print(f"The value passed to --bgp is invalid: {str(bgp)}.")
        print(f"Make sure the value passed is a valid ASN number of a valid IP Address/Subnet")
        return


def get_ip_or_none(ip_str):
    try:
        return ipaddress.ip_network(ip_str)
    except ValueError:
        return None


def fqdn(_fqdn: str, nameserver: str = None):
    rdtypes = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'SOA', 'PTR', 'SRV', 'TXT', 'CAA', 'DS', 'DNSKEY', 'RRSIG', 'NSEC',
               'NSEC3', 'NSEC3PARAM']
    console = Console()

    system_nameservers = []
    try:
        # Set up resolver
        if nameserver:
            console.print(f"[bold]FQDN:[/bold] {_fqdn}, [bold]Nameserver:[/bold] {nameserver}")
            resolver.default_resolver = resolver.Resolver(configure=False)
            resolver.default_resolver.nameservers = [nameserver]
        else:
            resolver.default_resolver = resolver.Resolver()
            system_nameservers = resolver.default_resolver.nameservers
            console.print(
                f"[bold]FQDN:[/bold] {_fqdn}, [bold]Nameserver:[/bold] {system_nameservers[0] if system_nameservers else 'unknown'}")

        # Create a table
        table = Table(
            title=f"DNS Records for {_fqdn} using nameserver: {nameserver if nameserver else system_nameservers[0]}",
            show_lines=True)
        table.add_column("Record Type", style="cyan")
        table.add_column("Data", style="green")
        table.add_column("Status", style="yellow")

        # Collect DNS data
        for rdtype in rdtypes:
            try:
                answers = resolver.resolve(_fqdn, rdtype)
                for rdata in answers:
                    table.add_row(rdtype, str(rdata), "✓")
            except Exception as e:
                error_msg = str(e)
                # Only add to table if it's not a "record not found" type error
                if "NXDOMAIN" not in error_msg and "NODATA" not in error_msg:
                    table.add_row(rdtype, "", f"Error: {error_msg}")

        # Display the table
        console.print(table, new_line_start=True)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return


if __name__ == "__main__":
    parser = ArgumentParser('''A network tool for capturing information about network stuff
    This tool accepts a variety of arguments to perform different network-related tasks.''')
    parser.add_argument("--fqdn", type=str, nargs=1, help='''Enter the FQDN of the target host.''')
    parser.add_argument("--nameserver", type=str, nargs=1, help='''Enter the nameserver to use for DNS queries.''')
    parser.add_argument("--subnet", type=str, nargs=1, help='''Enter the IP/subnet address of the target host.''')
    parser.add_argument("--target-host", type=str, nargs=1, help='''Enter the target host to 
                        scan including the port number for example 10.0.0.1:80''')
    parser.add_argument("--bgp", type=str, help='''Enter the subnet or ASN you wish to inspect.''')
    main(parser.parse_args())
