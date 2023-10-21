from .__baseUnits__ import BaseUnit
from .parse import parse_units

class Units:

    __name__ = "unit"

    def __init__(self, string: str = "", base_units: list[BaseUnit] = [], parse = True):
        self.string: str = string
        self.base_units: list[BaseUnit] = []

        if parse:
            self.string, self.base_units = parse_units(string)
        else:
            self.base_units = self.flatten(base_units)

        # Take out any BaseUnits with an exponent of 0
        i = 0
        while i < len(self.base_units):
            if self.base_units[i].exp == 0:
                self.base_units.pop(i)
            else:
                i += 1

        self.dimension = " ".join([f"{u.dimension}^{u.exp}" for u in self.base_units])

    def __str__(self):
        if self.is_unitless():
            return "(unitless)"
        
        string = []
        for u in sorted(self.base_units, reverse=True):
            string.append(str(u))
        
        return " ".join(string)
    
    def __mul__(self, other):
        new = Units()
        if isinstance(other, BaseUnit):
            for u in self.base_units:
                if u == other:
                    u = u * other
                if u:
                    new.base_units.append(u)
            if other not in self.base_units:
                new.base_units.append(other)      

        else:
            for u in self.base_units:
                if u in other.base_units:
                    same = [x for x in other.base_units if x == u][0]
                    u = u * same
                if u:
                    new.base_units.append(u)
            for u in other.base_units:
                if not u in self.base_units:
                    new.base_units.append(u)

        return new
    
    def __truediv__(self, other):
        temp = other.invert()
        return self * temp
    
    def is_unitless(self):
        return len(self.base_units) == 0

    def flatten(self, lst) -> list[BaseUnit]:
        return_lst: list[BaseUnit] = []
        for u in lst:
            if isinstance(u, Units) and u.base_units:
                return_lst.extend(u.base_units)
            else:
                return_lst.append(u)
        return return_lst
    
    def update_exp(self, exp):
        for u in self.base_units:
            u.update_exp(exp)

    def invert(self):
        new = self.copy()
        for u in new.base_units:
            u.update_exp(-1)
        return new

    def copy(self):
        new = Units(string = self.string, parse=False)
        for u in self.base_units:
            new.base_units.append(u.copy())
        return new
    
    def simplify(self):
        remaining = self.base_units.copy()
        keep = []
        modifier = 1
        while len(remaining) > 0:
            canceled = False
            u = remaining.pop(0)

            i = 0
            while i < len(remaining):
                if can_convert(u * remaining[i]):
                    other = remaining.pop(i)
                    modifier *= other.mod() / u.mod()
                    canceled = True
                    break
                elif can_convert(u / remaining[i]):
                    other = remaining.pop(i)
                    modifier /= other.mod() * u.mod()
                    u.exp += other.exp
                else:
                    i += 1

            if not canceled:
                keep.append(u)
        return Units(base_units=keep, parse=False), modifier


class Value:

    __use_sigfigs__ = False

    def __init__(self, number, units, sigfigs = None):
        self.num = float(number) if number else number

        if not isinstance(units, Units):
            units = Units(units)
        self.units = units

        if sigfigs is None:
            sigfigs = count_sigfigs(number)
        self.sigfigs = sigfigs

    def __repr__(self):
        return f"Value({self.num}, '{self.units}')"
    
    def __str__(self):
        if self.__use_sigfigs__:
            return f"{self.roundsf().num} {self.units}"
        return f"{self.num} {self.units}"
    
    def __eq__(self, other):
        return self.equals(other)
    
    def __lt__(self, other):
        if not isinstance(other, Value):
            raise TypeError("Can only compare against another value object")
        other = other.convert_units(self.units)
        return self.num < other.num
    
    def __gt__(self, other):
        if not isinstance(other, Value):
            raise TypeError("Can only compare against another value object")
        other = other.convert_units(self.units)
        return self.num > other.num
    
    def __add__(self, other):
        if isinstance(other, int) or isinstance(other, float):
            return Value(self.num + other, self.units, self.sigfigs)
        other = other.convert_units(self.units)
        return Value(self.num + other.num, self.units, min([self.sigfigs, other.sigfigs]))
    
    def __radd__(self, other):
        if not (isinstance(other, int) or isinstance(other, float)):
            raise TypeError()
        return self.__add__(other)
    
    def __sub__(self, other):
        if isinstance(other, int) or isinstance(other, float):
            return Value(self.num - other, self.units, self.sigfigs)
        other = other.convert_units(self.units)
        return Value(self.num - other.num, self.units, min([self.sigfigs, other.sigfigs]))
    
    def __rsub__(self, other):
        if not (isinstance(other, int) or isinstance(other, float)):
            raise TypeError()
        return Value(other - self.num, self.units, self.sigfigs)
    
    def __mul__(self, other):
        if isinstance(other, int) or isinstance(other, float):
            return Value(self.num * other, self.units, self.sigfigs)
        return Value(self.num * other.num, self.units * other.units, min([self.sigfigs, other.sigfigs]))
    
    def __rmul__(self, other):
        if not (isinstance(other, int) or isinstance(other, float)):
            raise TypeError()
        return self.__mul__(other)
    
    def __truediv__(self, other):
        if isinstance(other, int) or isinstance(other, float):
            return Value(self.num / other, self.units, self.sigfigs)
        return Value(self.num / other.num, self.units / other.units, min([self.sigfigs, other.sigfigs]))
    
    def __rtruediv__(self, other):
        if not (isinstance(other, int) or isinstance(other, float)):
            raise TypeError()
        return Value(other / self.num, self.units.invert(), self.sigfigs)
    
    def __pow__(self, exp):
        if isinstance(exp, Value):
            exp = exp.num
        return Value(self.num ** exp, self.units.update_exp(exp), self.sigfigs)
    
    def __round__(self, n):
        new = self.copy()
        new.num = round(new.num, n)
        return new
    
    def roundsf(self):
        if self.num:
            import sigfig
            return Value(sigfig.round(self.num, sigfigs = self.sigfigs), self.units, self.sigfigs)
        return self
    
    def equals(self, other, epsilon = 0.005):
        if not isinstance(other, Value):
            raise TypeError("Can only compare against another value object")
        other = other.convert_units(self.units)
        return abs((self.num - other.num) / self.num) < epsilon
    
    def copy(self):
        new = Value(self.num, self.units.copy(), self.sigfigs)
        return new
    
    def convert_units(self, new_units, mw = None):
        if not isinstance(new_units, Units):
            new_units = Units(new_units)

        converter_units: Units = new_units / self.units

        if converter_units.is_unitless():
            return Value(self.num, self.units, self.sigfigs)

        needs_mw = False
        if not can_convert(converter_units):
            mw_units = Units("g/mol")
            if can_convert(converter_units * mw_units):
                if mw is None:
                    raise Exception(f"Needs the molecular weight to convert but no molecular weight was provided.")
                needs_mw = True
                mw = 1 / mw
            elif can_convert(converter_units / mw_units):
                if mw is None:
                    raise Exception(f"Needs the molecular weight to convert but no molecular weight was provided.")
                needs_mw = True
            else:
                raise Exception(f"The units ({self.units}) can't be converted to the new units ({new_units})")

        conversion_factor = build_conversion_factor(converter_units, mw, needs_mw)
        new = self * conversion_factor
        new.sigfigs = self.sigfigs
        return new
    
    def to(self, new_units, mw = None):
        return self.convert_units(new_units, mw)
    
    def simplify_units(self):
        new_units, modifier = self.units.simplify()
        return Value(self.num * modifier, new_units, self.sigfigs)
 
    
def use_sigfigs():
    try:
        import sigfig
        Value.__use_sigfigs__ = True
    except ModuleNotFoundError:
        print("The sigfig module was not found. Sigfig rounding will not be used.")


def can_convert(units):
    dimensions = {}
    for u in units.base_units:
        if not u.dimension in dimensions:
            dimensions[u.dimension] = 0
        dimensions[u.dimension] += u.exp
    return all(v == 0 for v in dimensions.values())


def build_conversion_factor(converter_units, mw: Value, needs_mw):
    factor = Value(1, None)
    if needs_mw:
        converter_units /= mw.units
        factor *= mw
    for u in converter_units.base_units:
        factor *= Value(u.mod(), u)
    return factor


def count_sigfigs(number):
    number = str(number).lstrip("-").split("e")[0]
    integer, _, decimal = number.partition(".")
    if decimal:
        return len((integer + decimal).lstrip("0"))
    return len(integer.strip("0"))