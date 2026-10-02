# Discovery note

Neha needs to identify recurring customer-reported product issues without manually reading every Other comment. The unit of analysis is one returned order; no sales denominator is supplied.

The source is the user-supplied synthetic workbook. It has 1,000 return records, including 440 Other comments. The 31% overall return rate is context from the brief, not a rate measurable in this file. The workbook's README and validation summary are supporting context, not inference input.

The decision workflow is: inspect a recurring reason, select a SKU/vendor/category, read the source evidence, resolve uncertain rows, and export. Findings are investigation candidates; the app makes no automatic catalogue, refund or vendor changes.

Known data limitation: the evaluation sub-taxonomy includes `defect`, aliased to `general_defect` after inference. Some synthetic sub-labels are not strongly supported by their comments. The evaluator preserves those disagreements rather than tuning predictions to hidden truth.

Before production, confirm whether there are multiple reasons per return, obtain units sold by SKU/vendor, agree a review owner and queue SLA, assess a manually adjudicated sample, and define customer-data retention and access controls. None blocks demonstrating this synthetic MVP.
