"""Local release backup/restore helper. Requires an authorized AWS CLI environment."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import zipfile

HEADERS = {'ContentType': '--content-type', 'CacheControl': '--cache-control',
           'ContentEncoding': '--content-encoding', 'ContentDisposition': '--content-disposition',
           'ContentLanguage': '--content-language', 'Expires': '--expires'}


def aws(*args):
    return json.loads(subprocess.check_output(['aws', *args, '--output', 'json']))


def backup(directory, function, bucket):
    directory.mkdir(parents=True, exist_ok=False)
    current = aws('lambda', 'get-function', '--function-name', function)
    config = current['Configuration']
    if config.get('PackageType') != 'Zip' or config['Handler'] != 'cloud.aws_handler.handler':
        raise ValueError('Unexpected Lambda package/handler. Inspect before deploying.')
    if config.get('LastUpdateStatus') != 'Successful':
        raise ValueError('Lambda has an update in progress or failed; inspect first.')
    payload = urllib.request.urlopen(current['Code']['Location'], timeout=60).read()
    if base64.b64encode(hashlib.sha256(payload).digest()).decode() != config['CodeSha256']:
        raise ValueError('Lambda backup checksum mismatch.')
    (directory / 'lambda-before.zip').write_bytes(payload)
    with zipfile.ZipFile(directory / 'lambda-before.zip') as archive:
        if archive.testzip():
            raise ValueError('Invalid Lambda ZIP.')
    (directory / 'lambda-configuration.json').write_text(json.dumps(config, indent=2))
    listing = aws('s3api', 'list-objects-v2', '--bucket', bucket)
    manifest = []
    for i, obj in enumerate(listing.get('Contents', [])):
        target = directory / f'object-{i:05d}'
        headers = aws('s3api', 'get-object', '--bucket', bucket, '--key', obj['Key'], str(target))
        manifest.append({'key': obj['Key'], 'file': target.name, 'headers': headers})
    if not any(obj['key'] == 'index.html' for obj in manifest):
        raise ValueError('Frontend backup lacks index.html; check the bucket.')
    (directory / 'frontend-manifest.json').write_text(json.dumps({'bucket': bucket, 'objects': manifest}, indent=2))
    (directory / 'BACKUP_COMPLETE').write_text('Lambda ZIP checksum and frontend downloads verified.\n')
    print(f'Backup complete: {directory.resolve()}')


def restore(directory, bucket):
    if not (directory / 'BACKUP_COMPLETE').exists():
        raise ValueError('Backup is incomplete. Stop and inspect.')
    manifest = json.loads((directory / 'frontend-manifest.json').read_text())
    if bucket != manifest['bucket']:
        raise ValueError('Backup bucket differs from target bucket.')
    # Restore assets before entrypoints. Leave new extra objects harmlessly in place.
    for obj in sorted(manifest['objects'], key=lambda o: o['key'] in ('index.html', 'config.js')):
        args = ['s3api', 'put-object', '--bucket', bucket, '--key', obj['key'],
                '--body', str(directory / obj['file'])]
        headers = obj['headers']
        for header, option in HEADERS.items():
            if header in headers:
                args.extend([option, str(headers[header])])
        if headers.get('Metadata'):
            args.extend(['--metadata', json.dumps(headers['Metadata'])])
        aws(*args)
    print('Frontend restored with original content headers and custom metadata. Invalidate CloudFront next.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore-frontend'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--function', default='musa-game-handler')
    options = parser.parse_args()
    if options.action == 'backup':
        backup(options.directory, options.function, options.bucket)
    else:
        restore(options.directory, options.bucket)
