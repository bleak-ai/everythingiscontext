---
description: Draft a refund reply for a customer, following the support workflow
parameters:
  - name: email
    description: The customer's email address
    required: true
---
A customer with email $email asked for a refund. Follow the support workflow
in modules/support-workflow/steps.md: look the customer up in stripe first,
then draft a reply using the closest playbook under
modules/support-workflow/playbooks/. Show the draft to the user before
anything is sent or refunded.
