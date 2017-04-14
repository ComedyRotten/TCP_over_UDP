import binascii

'''
Modified Checksum
Editors: Reuben Sonnenberg and Devon Olson
'''

# Assumes last field is the checksum!
def validate_checksum(message):
    try:
        msg,reported_checksum = message.rsplit(b'|',1)
        msg += b'|'
        return generate_checksum(msg) == reported_checksum
    except:
        return False

# Assumes message does NOT contain final checksum field. Message MUST end
# with a trailing '|' character.
def generate_checksum(message):
    return (str(binascii.crc32(message) & 0xffffffff).encode())