## Button Command (`/button`)

- format message with button

## Example Usage

- Reply a message with `/button` command
- Message after `/button` command
  ```txt
  /button This is a message with button

  [GitHub](buttonurl://[URL])
  ```

## Formatting

- Normal button format:
  ```txt
  [Text](buttonurl://[URL])
  ```

- Primary button format:
  ```txt
  [Text](buttonurl#primary://[URL])
  ```

- Success button format:
  ```txt
  [Text](buttonurl#success://[URL])
  ```

- Danger button format:
  ```txt
  [Text](buttonurl#danger://[URL])
  ```

- Same line with last button:
  ```txt
  [Button 1](buttonurl://[URL])
  [Button 2](buttonurl://[URL]:same)
  ```
