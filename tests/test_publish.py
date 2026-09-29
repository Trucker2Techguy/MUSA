"""Checks upload order and invalidation without calling AWS."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublishTests(unittest.TestCase):
    def test_upload_sets_entrypoint_metadata_then_invalidates_and_waits(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'aws'
            log = Path(directory) / 'calls'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MUSA_TEST_AWS_LOG"\n'
                            'if [ "$1 $2" = "cloudfront create-invalidation" ]; then echo INV-123; fi\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ['PATH'], MUSA_TEST_AWS_LOG=str(log))
            subprocess.run(['bash', 'scripts/publish_frontend.sh', 'wss://example.test/prod',
                            'example-bucket', 'EXAMPLEDIST'], cwd=ROOT, env=env, check=True, capture_output=True)
            calls = log.read_text().splitlines()
            self.assertEqual([line.split()[:2] for line in calls],
                             [['s3', 'sync'], ['s3', 'cp'], ['s3', 'cp'],
                              ['cloudfront', 'create-invalidation'], ['cloudfront', 'wait']])
            self.assertTrue(all('no-store, max-age=0' in line for line in calls[1:3]))
            self.assertIn('/ /index.html /config.js', calls[3])
            self.assertIn('--id INV-123', calls[4])

if __name__ == '__main__':
    unittest.main()
