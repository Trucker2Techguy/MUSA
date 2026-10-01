# Build 0.2 — exact local deployment and rollback sequence

Deployment approved by the owner, but not performed from the Work workspace. GitHub push was attempted and failed because no GitHub credentials are available here. All changes are committed locally; the supplied Git bundle can transfer this branch into your existing checkout.

Run the following in **Bash in your existing authenticated AWS environment**, from the MUSA repository root. Requirements: AWS CLI v2, Python 3, Node, Git, and curl. On Windows, use the authorized Git Bash/WSL environment where these commands and your AWS credentials already work. These are instructions to run locally; no AWS commands below were executed in Work.

## 1. Get the approved branch

If the branch has been pushed after GitHub connection:

```bash
git status --short
# Stop if you have uncommitted work; commit/stash it first.
git fetch origin
git switch --track origin/build-0.2
# If the local branch already exists instead:
# git switch build-0.2
# git pull --ff-only origin build-0.2
```

If the push is still blocked, download `MUSA-build-0.2.bundle`, put it outside the repository, then run:

```bash
git status --short
# Stop if you have uncommitted work.
git bundle verify /path/to/MUSA-build-0.2.bundle
git fetch /path/to/MUSA-build-0.2.bundle build-0.2:refs/remotes/work/build-0.2
git switch -c build-0.2 --track work/build-0.2
# If build-0.2 already exists: switch to it and merge --ff-only work/build-0.2.
git push -u origin build-0.2
```

Use the actual downloaded bundle path. Do not replace your checkout with only the README; the whole branch contains the implementation and tests.

## 2. Validate and discover the existing resources

Keep this shell open for all later steps. Stop on errors.

```bash
set -euo pipefail
export AWS_DEFAULT_REGION=us-east-1
export AWS_PAGER=""
# If you normally use a named profile, set it now:
# export AWS_PROFILE=your-existing-profile
aws sts get-caller-identity

git branch --show-current
git rev-parse HEAD
python3 -m unittest discover -s tests -v
node tests/test_saved_session.cjs
node --check static/app.js
node --check static/realtime.js
bash -n scripts/publish_frontend.sh
git diff --check

MUSA_FUNCTION=musa-game-handler
MUSA_STACK=$(aws cloudformation describe-stack-resources \
  --physical-resource-id "$MUSA_FUNCTION" \
  --query 'StackResources[0].StackName' --output text)
test -n "$MUSA_STACK" && test "$MUSA_STACK" != None
aws cloudformation describe-stacks --stack-name "$MUSA_STACK" \
  --query 'Stacks[0].Outputs' --output table

MUSA_WS=$(aws cloudformation describe-stacks --stack-name "$MUSA_STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketUrl'].OutputValue | [0]" --output text)
MUSA_BUCKET=$(aws cloudformation describe-stacks --stack-name "$MUSA_STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue | [0]" --output text)
MUSA_CF=$(aws cloudformation describe-stacks --stack-name "$MUSA_STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontId'].OutputValue | [0]" --output text)
[[ "$MUSA_WS" == wss://* ]]
test -n "$MUSA_BUCKET" && test "$MUSA_BUCKET" != None
test -n "$MUSA_CF" && test "$MUSA_CF" != None
printf 'Stack: %s\nBucket: %s\nCloudFront: %s\nWebSocket: %s\n' \
  "$MUSA_STACK" "$MUSA_BUCKET" "$MUSA_CF" "$MUSA_WS"
```

Confirm the account and resources are your existing production M.U.S.A. resources. If stack discovery fails, find the existing stack name in CloudFormation, set `MUSA_STACK` to that name, and rerun the output commands. Do not create a new stack. This release updates existing code/assets only; no SAM deployment, DNS update, or resource changes are needed. Direct Lambda code updates should also be reflected in the source used for future SAM deployments so a later stack deployment does not restore older code.

## 3. Back up the current Lambda and frontend before changing either

Choose a private local backup folder **outside the Git repository**. The configuration backup contains Lambda environment settings. Do not commit it.

```bash
MUSA_BACKUP="$(dirname "$PWD")/musa-backup-$(date -u +%Y%m%dT%H%M%SZ)"
export MUSA_BACKUP
python3 scripts/release_backup.py backup \
  --directory "$MUSA_BACKUP" --function "$MUSA_FUNCTION" --bucket "$MUSA_BUCKET"
test -f "$MUSA_BACKUP/BACKUP_COMPLETE"

aws cloudformation describe-stacks --stack-name "$MUSA_STACK" \
  --output json > "$MUSA_BACKUP/stack-before.json"
aws cloudfront get-distribution-config --id "$MUSA_CF" \
  --output json > "$MUSA_BACKUP/cloudfront-before.json"
aws s3 cp "s3://$MUSA_BUCKET/config.js" "$MUSA_BACKUP/config-before.js"
cat "$MUSA_BACKUP/config-before.js"
```

Confirm the backed-up production configuration uses the same WebSocket URL as `MUSA_WS`. The helper downloads the current Lambda ZIP using `get-function`, verifies its SHA-256 and ZIP integrity, saves configuration/revision ID, and backs up every frontend object plus content headers/custom metadata. Keep the folder intact. If any backup operation fails, do not deploy; use a new backup folder after fixing the error.

## 4. Package and update Lambda first

```bash
python3 - <<'PY'
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path.cwd()
files = [root / 'game.py', root / 'tictactoe.py', *sorted((root / 'cloud').glob('*.py'))]
with ZipFile(Path(os.environ['MUSA_BACKUP']) / 'lambda-build-0.2.zip', 'w', ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, path.relative_to(root).as_posix())
PY

MUSA_REVISION=$(python3 - <<'PY'
import json, os
from pathlib import Path
print(json.loads((Path(os.environ['MUSA_BACKUP']) / 'lambda-configuration.json').read_text())['RevisionId'])
PY
)

aws lambda update-function-code --function-name "$MUSA_FUNCTION" \
  --zip-file "fileb://$MUSA_BACKUP/lambda-build-0.2.zip" \
  --revision-id "$MUSA_REVISION" \
  --output json > "$MUSA_BACKUP/lambda-update-result.json"
aws lambda wait function-updated-v2 --function-name "$MUSA_FUNCTION"
aws lambda get-function-configuration --function-name "$MUSA_FUNCTION" \
  --query '{State:State,Update:LastUpdateStatus,Handler:Handler,Runtime:Runtime,Revision:RevisionId}' \
  --output table
```

The revision guard stops the update if Lambda changed since backup. Do not bypass it; take a fresh backup and inspect the competing change. The command updates the existing function's code, retaining environment variables, role, runtime, architecture, and API integration. Proceed only when State is `Active` and Update is `Successful`. Before uploading the frontend, open the existing site in two browser profiles and confirm the existing maze can still create/join/start/resume against the new backend. A failed check means stop and use backend rollback below.

## 5. Publish the frontend and wait for CloudFront

```bash
# Remove only generated output so stale build files cannot be uploaded.
python3 - <<'PY'
from pathlib import Path
import shutil
out = Path('dist')
if out.is_symlink():
    raise SystemExit('dist is a symlink; stop and inspect')
if out.exists():
    shutil.rmtree(out)
PY
bash scripts/publish_frontend.sh "$MUSA_WS" "$MUSA_BUCKET" "$MUSA_CF"
```

The publisher syncs the built frontend to the existing bucket, sets no-store metadata on HTML/config, invalidates `/`, `/index.html`, `/config.js`, `/realtime.js`, `/app.js`, and `/style.css`, and waits for invalidation completion. Keep the backups because the sync uses `--delete`.

## 6. Verify the live release

```bash
curl --fail --silent --show-error https://musa.jaimebsnyder.com/ \
  > "$MUSA_BACKUP/live-index-after.html"
python3 - <<'PY'
import os
from pathlib import Path
html = (Path(os.environ['MUSA_BACKUP']) / 'live-index-after.html').read_text()
for text in ('BUILD 0.2', '1 PLAYER / VS COMPUTER', '2 PLAYER / NETWORK',
             'ACCESS RESTRICTED // WOPR AUTHORIZATION REQUIRED'):
    assert text in html, text
print('Live HTML contains Build 0.2 and both Tic-Tac-Toe modes.')
PY
aws logs tail /aws/lambda/musa-game-handler --since 15m
```

In fresh browser profiles, verify:

- Solo starts without a partner, X produces a legal O response, outcome locks the board, refresh/resume restores state, and replay starts immediately.
- Network create/join uses the room type automatically; turns and occupied squares are enforced; both screens agree; win/draw, reconnect, and host replay work.
- Relay Recovery still creates/joins/plays/resumes and completes extraction. Resume an existing pre-release maze room if one is still valid.
- War remains disabled. Inspect the browser console and Lambda logs for errors.

Only after successful live verification, update the README's release status to deployed and record the verification. Do not claim live verification based on HTML checks alone.

## Frontend rollback (preferred if the new UI fails)

This restores prior files and metadata while leaving the compatible Build 0.2 backend in place for any active Tic-Tac-Toe rooms.

```bash
python3 scripts/release_backup.py restore-frontend \
  --directory "$MUSA_BACKUP" --bucket "$MUSA_BUCKET"
MUSA_INVALIDATION=$(aws cloudfront create-invalidation --distribution-id "$MUSA_CF" \
  --paths '/*' --query 'Invalidation.Id' --output text)
aws cloudfront wait invalidation-completed --distribution-id "$MUSA_CF" \
  --id "$MUSA_INVALIDATION"
```

Extra files added by Build 0.2 remain in the bucket but are not referenced by the old entrypoint. Old frontend files, MIME types, cache headers, encoding, and custom metadata are restored.

## Backend rollback (only when required)

Restore the frontend first. Build 0.1 cannot read new Tic-Tac-Toe rooms. Do not revert the backend while those sessions must remain usable. Stop creating new Tic-Tac-Toe rooms and wait for active rooms to expire, or explicitly accept ending those sessions. Do not delete room tables or restore stale room data.

```bash
MUSA_ROLLBACK_REVISION=$(aws lambda get-function-configuration \
  --function-name "$MUSA_FUNCTION" --query RevisionId --output text)
aws lambda update-function-code --function-name "$MUSA_FUNCTION" \
  --zip-file "fileb://$MUSA_BACKUP/lambda-before.zip" \
  --revision-id "$MUSA_ROLLBACK_REVISION" \
  --output json > "$MUSA_BACKUP/lambda-rollback-result.json"
aws lambda wait function-updated-v2 --function-name "$MUSA_FUNCTION"
aws lambda get-function-configuration --function-name "$MUSA_FUNCTION" \
  --query '{State:State,Update:LastUpdateStatus}' --output table
```

Retest Relay Recovery afterward. No configuration rollback is needed because this sequence changes Lambda code only. If you restart the shell, restore the saved values for `MUSA_BACKUP`, `MUSA_FUNCTION`, `MUSA_BUCKET`, and `MUSA_CF` before using rollback commands.
