# Regulatory and Model Governance Notes

This is a portfolio demonstration of selected good practices, not a compliance certification and not an endorsement by JPMorgan Chase.

## Demonstrated controls
- Synthetic-only data generation and documented provenance.
- Reproducible random seed.
- Schema, duplicate ID, timestamp, amount, and binary-label validation.
- Chronological model evaluation.
- Multiple evaluation metrics and a baseline comparison for forecasting.
- Read-only SQL explorer with basic query restrictions.
- Model limitations and intended-use documentation.
- Human-review requirement for any real-world use.

## Not implemented / not claimed
- Full enterprise access control, encryption/key management, retention/deletion workflows, production monitoring, comprehensive fairness assessment, independent model validation, or legal review.
- Compliance with any specific law, regulation, supervisory guidance, or JPMorgan Chase internal standard.

## Responsible use
Campaign scores should not be used to determine access to financial services. Predictive associations are not causal effects. Synthetic-data results should never be represented as production evidence.
