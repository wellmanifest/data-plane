"""The iterative canonical() must return the same bytes and raise the same first error as the original recursive form."""
import json
import random
import unittest
from collections import OrderedDict

from conformance.event_store import canonical
from conformance import line


def reference(value):
    """The recursive implementation shipped through 0.2.0, kept verbatim as the oracle."""
    def check(item):
        if isinstance(item,float): raise ValueError('Float is outside canonical profile')
        if isinstance(item,int) and not isinstance(item,bool) and abs(item)>2**53-1:
            raise ValueError('Large integers must use decimal strings')
        if isinstance(item,dict):
            if any(not isinstance(k,str) for k in item): raise ValueError('Non-string key')
            for val in item.values(): check(val)
        elif isinstance(item,list):
            for val in item: check(val)
    check(value)
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def outcome(fn, value):
    try: return ('ok', fn(value))
    except (ValueError, TypeError) as error: return (type(error).__name__, str(error))


def generate(rng, depth=0):
    leaves = [lambda: rng.choice(['', 'a', 'zażółć', '"\\', ' ']), lambda: rng.randint(-10, 10),
              lambda: rng.choice([2**53 - 1, -(2**53 - 1), 2**53, -(2**60)]), lambda: rng.choice([True, False, None]),
              lambda: rng.choice([0.5, float('nan')]), lambda: (1, 2)]
    if depth > 3 or rng.random() < 0.4: return rng.choice(leaves)()
    if rng.random() < 0.5: return [generate(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    keys = [rng.choice(['a', 'b', 'c', 'd', 'e']) for _ in range(rng.randint(0, 4))]
    value = {k: generate(rng, depth + 1) for k in keys}
    if rng.random() < 0.05: value[rng.randint(0, 3)] = 'x'
    return OrderedDict(value) if rng.random() < 0.1 else value


class CanonicalEquivalence(unittest.TestCase):
    def test_random_structures_match_reference(self):
        rng = random.Random(20261013); failures = 0
        for _ in range(20000):
            value = generate(rng)
            self.assertEqual(outcome(canonical, value), outcome(reference, value), repr(value)[:300])
            failures += outcome(reference, value)[0] != 'ok'
        self.assertGreater(failures, 1000)  # the corpus exercises every error path, not only valid input

    def test_line_module_uses_the_same_function(self):
        self.assertIs(line.canonical, canonical)


class ParsedRequest(unittest.TestCase):
    def test_parsed_argument_gives_the_same_envelope(self):
        contracts = line.load_contracts()
        text = ('resource.publish: process://data-gateway/resource.publish/v2 {"contentBase64":"aGVsbG8K",'
                '"idempotencyKey":"k","mediaType":"text/plain","requestId":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}')
        self.assertEqual(line.line_to_request(text, contracts, parsed=line.parse(text)), line.line_to_request(text, contracts))


if __name__ == '__main__':
    unittest.main()
