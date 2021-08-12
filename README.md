# Disclaimer

This deployment is NOT intended for a production environment, 'cause is a dumb Odoo module to send simple notifications trought Slack or Sendinblue. It's a work-in-progress on which some private modules were based and it's still in its early stages of development.

## Requirements

Compatible with Odoo 13.0
OCA queue_job module needed
SendInBlue account needed
Slack account needed

** Just setup a basic requirements.txt as usual: pip3 install -r requirements.txt **

### Kind of rapid instructions:

```
self.env.company.notify("an error notification", "[WARNING]", "<b>an example content</b>", channel)

First parameter is mandatory.
The default value for the second parameter is "NOTICE".\
The default value for the third parameter is the local IP address.
Then we have "sendiblue" and then we have "DEV".

Available channels are:
- sendinblue
- slack
- all (all previous together)

```

## Author

giuseppechecchia@gmail.com
