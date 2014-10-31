# meid.py - functions for handling Mobile Equipment Identifiers (MEIDs)
#
# Copyright (C) 2010, 2011, 2012, 2013 Arthur de Jong
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301 USA

"""MEID (Mobile Equipment Identifier).

The Mobile Equipment Identifier is used to identify a physical piece of
CDMA mobile station equipment.

>>> validate('AF 01 23 45 0A BC DE C')
'AF0123450ABCDE'
>>> validate('29360 87365 0070 3710 0')
'AF0123450ABCDE'
>>> validate('29360 87365 0070 3710 1')
Traceback (most recent call last):
    ...
InvalidChecksum: ...
>>> format('af0123450abcDEC', add_check_digit=True)
'AF 01 23 45 0A BC DE C'
>>> format('af0123450abcDEC', format='dec', add_check_digit=True)
'29360 87365 0070 3710 0'
"""

from stdnum.exceptions import *
from stdnum.util import clean


_hex_alphabet = '0123456789ABCDEF'


def _cleanup(number):
    """Remove any grouping information from the number and removes surrounding
    whitespace."""
    return clean(str(number), ' -').strip().upper()


def _ishex(number):
    for x in number:
        if x not in _hex_alphabet:
            return False
    return True


def _parse(number):
    number = _cleanup(number)
    if len(number) in (14, 15):
        # 14 or 15 digit hex representation
        if not _ishex(number):
            raise InvalidFormat()
        return number[0:14], number[14:]
    elif len(number) in (18, 19):
        # 18-digit decimal representation
        if not number.isdigit():
            raise InvalidFormat()
        return number[0:18], number[18:]
    else:
        raise InvalidLength()


def calc_check_digit(number):
    """Calculate the check digit for the number. The number should not
    already have a check digit."""
    # both the 18-digit decimal format and the 14-digit hex format
    # containing only decimal digits should use the decimal Luhn check
    from stdnum import luhn
    if number.isdigit():
        return luhn.calc_check_digit(number)
    else:
        return luhn.calc_check_digit(number, alphabet=_hex_alphabet)


def compact(number, strip_check_digit=True):
    """Convert the MEID number to the minimal (hexadecimal) representation.
    This strips grouping information, removes surrounding whitespace and
    converts to hexadecimal if needed. If the check digit is to be preserved
    and conversion is done a new check digit is recalculated."""
    # first parse the number
    number, cd = _parse(number)
    # strip check digit if needed
    if strip_check_digit:
        cd = ''
    # convert to hex if needed
    if len(number) == 18:
        number = '%08X%06X' % (int(number[0:10]), int(number[10:18]))
        if cd:
            cd = calc_check_digit(number)
    # put parts back together again
    return number + cd


def validate(number, strip_check_digit=True):
    """Checks to see if the number provided is a valid MEID number. This
    converts the representation format of the number (if it is
    decimal it is not converted to hexadecimal)."""
    from stdnum import luhn
    # first parse the number
    number, cd = _parse(number)
    if len(number) == 18:
        # decimal format can be easily determined
        if cd:
            luhn.validate(number + cd)
        # convert to hex
        manufacturer_code = int(number[0:10])
        serial_num = int(number[10:18])
        if manufacturer_code.bit_length() > 32 or serial_num.bit_length() > 24:
            raise InvalidComponent()
        number = '%08X%06X' % (manufacturer_code, serial_num)
        cd = calc_check_digit(number)
    elif number.isdigit():
        # if the remaining hex format is fully decimal it is an IMEI number
        from stdnum import imei
        imei.validate(number + cd)
    else:
        # normal hex Luhn validation
        if cd:
            luhn.validate(number + cd, alphabet=_hex_alphabet)
    if strip_check_digit:
        cd = ''
    return number + cd


def is_valid(number):
    """Checks to see if the number provided is a valid MEID number."""
    try:
        return bool(validate(number))
    except ValidationError:
        return False


def format(number, separator=' ', format=None, add_check_digit=False):
    """Reformat the passed number to the standard format. The separator
    used can be provided. If the format is specified (either 'hex' or
    'dec') the number is reformatted in that format, otherwise the current
    representation is kept. If add_check_digit is True a check digit will
    be added if it is not present yet."""
    # first parse the number
    number, cd = _parse(number)
    # format conversions if needed
    if format == 'dec' and len(number) == 14:
        # convert to decimal
        number = '%010d%08d' % (int(number[0:8], 16), int(number[8:14], 16))
        if cd:
            cd = calc_check_digit(number)
    elif format == 'hex' and len(number) == 18:
        # convert to hex
        number = '%08X%06X' % (int(number[0:10]), int(number[10:18]))
        if cd:
            cd = calc_check_digit(number)
    # see if we need to add a check digit
    if add_check_digit and not cd:
        cd = calc_check_digit(number)
    # split number according to format
    if len(number) == 14:
        number = [number[i * 2:i * 2 + 2]
                  for i in range(7)] + [cd]
    else:
        number = (number[:5], number[5:10], number[10:14], number[14:], cd)
    return separator.join(x for x in number if x)


def to_binary(number):
    """Convert the number to it's binary representation (without the check
    digit)."""
    import sys
    number = compact(number, strip_check_digit=True)
    if sys.version > '3':  # pragma: no cover (Python 2/3 specific code)
        return bytes.fromhex(number)
    else:  # pragma: no cover (Python 2/3 specific code)
        return number.decode('hex')


def to_pseudo_esn(number):
    """Convert the provided MEID to a pseudo ESN (pESN). The ESN is returned
    in compact hexadecimal representation."""
    import hashlib
    # return the last 6 digits of the SHA1  hash prefixed with the reserved
    # manufacturer code
    return '80' + hashlib.sha1(to_binary(number)).hexdigest()[-6:].upper()
