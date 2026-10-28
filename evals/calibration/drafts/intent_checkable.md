# Candidate samples for `intent_checkable`, for you to label

Each sample is a draft intent's acceptance criteria. Copy the ones you want into `evals/calibration/intent_checkable.toml` as
`[[samples]]` with `text = """DRAFT INTENT:\n..."""` and a `label` of `"pass"`, `"fail"` or `"unknown"`, by the rubric there.
None is labelled: the labels are yours.

## 1

- A customer who is locked out is told their account is locked
- No message, status or timing reveals whether an account exists
- Calls to support about "Login failed" fall

## 2

- Login feels faster and friendlier
- Support is happier

## 3

- A locked-out customer sees the lockout message on the login page
- Use the notification service to send the message
- The message is reviewed by legal

## 4

- Customers can log in

## 5

(no acceptance criteria)

## 6

- A customer who enters a wrong password three times is shown "Your account is locked" on the fourth attempt
- A visitor who enters a username that does not exist sees exactly the same page, in the same time, as one who enters a wrong password for a real account
- Support logs show a measurable drop in "Login failed" calls over the four weeks after release

## 7

- The problem is solved
- Legal is satisfied

## 8

- Locked-out customers are informed in a way legal approves
- The solution scales
