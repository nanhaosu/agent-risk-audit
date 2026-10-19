import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jrh_export as m


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(source_id='scene', case_id='case', linkage_state='unresolved',
                         representation='canonical', repeat_id=1, condition='full_context',
                         prompt_sha256='a'*64)
        self.good = dict(example_id='case', condition='full_context', status='ok',
                         prompt_sha256='a'*64, response_text='{"risk_severity": 4}')

    def test_missing_and_failure_are_not_zero(self):
        rows = m.convert([self.plan], [], 1, 'ledger')
        self.assertEqual(rows[0]['status'], 'missing')
        rows = m.convert([self.plan], [dict(self.good, status='error', error='timeout')], 1, 'ledger')
        self.assertEqual(rows[0]['status'], 'transport_error')
        self.assertIsNone(rows[0]['autograder_score'])

    def test_duplicates_preserved_without_selection(self):
        rows = m.convert([self.plan], [self.good, self.good], 1, 'ledger')
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['duplicate_response'] for r in rows))
        self.assertEqual([r['ledger_line'] for r in rows], [1, 2])

    def test_invalid_and_hash_mismatch(self):
        for text in ['{"risk_severity": true}', '{"risk_severity": 0}', 'broken']:
            self.assertEqual(m.convert([self.plan], [dict(self.good, response_text=text)], 1, 'l')[0]['status'], 'parse_error')
        row=m.convert([self.plan], [dict(self.good, prompt_sha256='b'*64)], 1, 'l')[0]
        self.assertEqual(row['status'], 'prompt_mismatch')
        self.assertIsNone(row['autograder_score'])

    def test_unexpected_and_malformed_retained(self):
        rows=m.convert([self.plan], [dict(self.good, example_id='other'), 'bad line'], 1, 'l')
        self.assertEqual(len(rows), 3)
        self.assertEqual({r['status'] for r in rows}, {'ok','malformed_record','missing'})
        self.assertFalse(rows[0]['planned'])
        self.assertIsNone(rows[0]['source_id'])

    def test_no_inferred_risk_gold(self):
        row=m.convert([self.plan], [self.good], 1, 'l')[0]
        self.assertEqual(row['autograder_score'],4)
        self.assertIsNone(row['validation_score'])
        self.assertEqual(row['source_id'],'scene')

    def test_duplicate_plan_rejected(self):
        with self.assertRaises(ValueError):
            m.convert([self.plan,self.plan], [], 1, 'l')

if __name__ == '__main__': unittest.main()
