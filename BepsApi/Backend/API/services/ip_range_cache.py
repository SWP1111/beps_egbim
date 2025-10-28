from models import IpRange
import ipaddress

ip_range_list = [] # List to store IPRange objects

def load_ip_ranges():
    ranges = IpRange.query.all()  # Fetch all IpRange objects from the database
    return [(ipaddress.ip_address(r.start_ip), ipaddress.ip_address(r.end_ip)) for r in ranges]

def initialize_ip_ranges():
    global ip_range_list
    ip_range_list[:] = load_ip_ranges()  # Load IP ranges into the global list