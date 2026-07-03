#!/usr/bin/env bash
# End-to-end smoke test: upload a declaration, wait for the pipeline,
# print the validation report.
#
# Usage: ./smoke_test.sh path/to/declaration.pdf [stack-name]
set -euo pipefail

PDF="${1:?Usage: smoke_test.sh path/to/declaration.pdf [stack-name]}"
STACK="${2:-customs-analyzer}"

out() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

BUCKET="$(out BucketName)"
TABLE="$(out DeclarationsTableName)"
ID="smoke-$(date +%s)"
EXT="${PDF##*.}"

echo "-> uploading as input/$ID.$EXT to s3://$BUCKET"
aws s3 cp "$PDF" "s3://$BUCKET/input/$ID.$EXT" --only-show-errors

echo -n "-> waiting for pipeline"
STATUS="?"
for _ in $(seq 1 60); do
  STATUS="$(aws dynamodb get-item --table-name "$TABLE" \
    --key "{\"declaration_id\":{\"S\":\"$ID\"}}" \
    --query 'Item.status.S' --output text 2>/dev/null || echo '?')"
  case "$STATUS" in
    VALIDATED|FLAGGED|ERROR) break ;;
    *) echo -n "."; sleep 3 ;;
  esac
done
echo ""
echo "-> status: $STATUS"

if [ "$STATUS" = "VALIDATED" ] || [ "$STATUS" = "FLAGGED" ]; then
  echo "-> report:"
  aws s3 cp "s3://$BUCKET/reports/$ID.json" - --only-show-errors \
    | python3 -m json.tool
fi
