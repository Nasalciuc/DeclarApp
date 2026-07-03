#!/usr/bin/env bash
# Safety net FIRST: monthly cost budget with alerts at $20 / $50 / $100
# (10% / 25% / 50% of a $200 limit). Run before deploying anything.
#
# Usage: ./set_budgets.sh you@example.com [limit_usd]
set -euo pipefail

EMAIL="${1:?Usage: set_budgets.sh you@example.com [limit_usd]}"
LIMIT="${2:-200}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

BUDGET=$(cat <<JSON
{
  "BudgetName": "customs-analyzer-credits",
  "BudgetType": "COST",
  "TimeUnit": "MONTHLY",
  "BudgetLimit": { "Amount": "${LIMIT}", "Unit": "USD" }
}
JSON
)

NOTIFICATIONS=$(cat <<JSON
[
  { "Notification": { "NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN",
      "Threshold": 10, "ThresholdType": "PERCENTAGE" },
    "Subscribers": [ { "SubscriptionType": "EMAIL", "Address": "${EMAIL}" } ] },
  { "Notification": { "NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN",
      "Threshold": 25, "ThresholdType": "PERCENTAGE" },
    "Subscribers": [ { "SubscriptionType": "EMAIL", "Address": "${EMAIL}" } ] },
  { "Notification": { "NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN",
      "Threshold": 50, "ThresholdType": "PERCENTAGE" },
    "Subscribers": [ { "SubscriptionType": "EMAIL", "Address": "${EMAIL}" } ] }
]
JSON
)

aws budgets create-budget \
  --account-id "$ACCOUNT_ID" \
  --budget "$BUDGET" \
  --notifications-with-subscribers "$NOTIFICATIONS"

echo "Budget 'customs-analyzer-credits' set: alerts to $EMAIL at" \
     "\$$((LIMIT / 10)), \$$((LIMIT / 4)), \$$((LIMIT / 2)) of \$$LIMIT."
