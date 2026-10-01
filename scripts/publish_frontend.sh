#!/usr/bin/env bash
# Run only after an approved stack deployment. Inputs are stack outputs.
set -euo pipefail
if [[ $# -ne 3 ]]; then
  echo 'Usage: publish_frontend.sh <WebSocketUrl> <BucketName> <CloudFrontId>' >&2
  exit 2
fi
websocket_url=$1
bucket_name=$2
distribution_id=$3
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)
python3 "$script_dir/build_frontend.py" --websocket-url "$websocket_url" --output "$project_dir/dist"
aws s3 sync "$project_dir/dist/" "s3://$bucket_name/" --delete
# Metadata applies even to direct origin reads; invalidate the already-cached paths too.
aws s3 cp "$project_dir/dist/index.html" "s3://$bucket_name/index.html" --content-type 'text/html; charset=utf-8' --cache-control 'no-store, max-age=0'
aws s3 cp "$project_dir/dist/config.js" "s3://$bucket_name/config.js" --content-type 'application/javascript; charset=utf-8' --cache-control 'no-store, max-age=0'
invalidation_id=$(aws cloudfront create-invalidation --distribution-id "$distribution_id" --paths '/' '/index.html' '/config.js' '/realtime.js' '/app.js' '/style.css' --query 'Invalidation.Id' --output text)
aws cloudfront wait invalidation-completed --distribution-id "$distribution_id" --id "$invalidation_id"
