"""Public response projection. Never modifies the authoritative source records."""
REDACTED = '未核验，已隐藏'
PRIVATE_FIELDS = {'订单地址', 'address', 'shipping_address', 'customer_address'}

def public_data(value, addresses=()):
    if isinstance(value, dict):
        return {k: REDACTED if k in PRIVATE_FIELDS and v else public_data(v, addresses) for k,v in value.items()}
    if isinstance(value, list):
        return [public_data(v, addresses) for v in value]
    if isinstance(value, str):
        for address in addresses:
            if address:
                value = value.replace(address, REDACTED)
                for line in address.splitlines():
                    if any(ch.isdigit() for ch in line) and len(line.strip()) >= 5:
                        value = value.replace(line.strip(), REDACTED)
        return value
    return value
