#!/usr/bin/env python3
from network_tool import fqdn

# Test with just FQDN (should use system nameserver)
print("Testing with just FQDN (using system nameserver):")
fqdn("google.com")