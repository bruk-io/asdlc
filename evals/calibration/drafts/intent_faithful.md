# Candidate samples for `intent_faithful`, for you to label

Each sample is a request and a draft intent, as the judge will see them. Copy the ones you want into
`evals/calibration/intent_faithful.toml` as `[[samples]]` with `text = """..."""` and `label = "pass"`, `"fail"` or
`"unknown"`, by your reading of the rubric there. I wrote them to span the answers; none is labelled, because the labels
are yours. Change or drop any you would not have written.

The request used in every sample:

> Our support team keeps telling me the same thing: when a customer fails to log in they just see "Login failed" and phone
> us. About a third of their calls are that. They want customers to be told when it's because the account is locked, but
> legal says we can never reveal whether an account exists. I don't know how we'd do both.

## 1

Problem: Customers who fail to log in only see "Login failed" and phone support; about a third of support's calls are that. Support wants customers told when the account is locked, but legal says we can never reveal whether an account exists.
Constraints: Legal: we can never reveal whether an account exists.
Open questions: How can a locked-out customer be told without revealing whether an account exists?

## 2

Problem: Users experience friction at login and the support team handles a high volume of authentication-related contacts. The login experience should be improved.
Constraints: Comply with legal requirements.
Open questions: None.

## 3

Problem: Customers who fail to log in only see "Login failed". Support gets many calls.
Constraints: None.
Open questions: None.

## 4

Problem: Customers who fail to log in only see "Login failed" and phone support; about a third of support's calls are that. We should add a "your account is locked" email sent when an account locks, using the notification service.
Constraints: Legal: we can never reveal whether an account exists.
Open questions: Which email template to use?

## 5

Problem: Customers who fail to log in only see "Login failed" and phone support; about 60% of support's calls are that. Support wants customers told when the account is locked, but legal says we can never reveal whether an account exists.
Constraints: Legal: we can never reveal whether an account exists.
Open questions: How can a locked-out customer be told without revealing whether an account exists?

## 6

(an empty draft)

## 7

Problem: When a customer fails to log in they see "Login failed" and phone us, about a third of support's calls. Support wants those customers told when the cause is a locked account. Legal's rule: never reveal whether an account exists.
Constraints: Legal's rule above.
Open questions: Nobody knows how to do both: telling a locked-out customer and not revealing whether the account exists.

## 8

Problem: Implement a lockout status endpoint returning ACCOUNT_LOCKED so the login page can display a message.
Constraints: Legal: we can never reveal whether an account exists.
Open questions: None.
