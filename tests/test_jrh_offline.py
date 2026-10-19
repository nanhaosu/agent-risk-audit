import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jrh_offline import qualify


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.p=dict(source_id='s',case_id='c',condition='full_context',repeat_id=1,
                    linkage_state='confirmed',representation='canonical',prompt_sha256='a'*64)
        self.r=dict(self.p,planned=True,duplicate_response=False,status='ok',autograder_score=3,
                    raw_record=dict(example_id='c',condition='full_context',status='ok',
                                    prompt_sha256='a'*64,response_text='{"risk_severity":3}'))
    def test_valid(self):
        self.assertEqual(qualify([self.r],[self.p])[0]['exclusion_reasons'],[])
    def test_failures_missing_and_unexpected(self):
        for status in ['transport_error','missing','parse_error','prompt_mismatch']:
            self.assertFalse(qualify([dict(self.r,status=status)],[self.p])[0]['eligible'])
        self.assertFalse(qualify([self.r,dict(self.r,case_id='other')],[self.p])[1]['eligible'])
    def test_unflagged_duplicates_all_excluded(self):
        rows=qualify([self.r,dict(self.r,autograder_score=4)],[self.p])
        self.assertTrue(all(not r['eligible'] for r in rows))
        self.assertTrue(all('duplicate_slot' in r['exclusion_reasons'] for r in rows))
    def test_raw_and_metadata_checked(self):
        for change in [dict(source_id='wrong'),dict(autograder_score=True),dict(planned=False),
                       dict(raw_record=dict(self.r['raw_record'],status='error'))]:
            self.assertFalse(qualify([dict(self.r,**change)],[self.p])[0]['eligible'])
    def test_missing_export_row_rejected(self):
        with self.assertRaises(ValueError): qualify([], [self.p])

if __name__=='__main__':unittest.main()
