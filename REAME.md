TPN is a dumb Odoo module to send simple notifications trought Slack or Sendinblue.
It is a work-in-progress on which some private modules were based and it's still in its early stages of development. Currently only contains few pieces of codes: using it on production is not reccomanded.

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
- akeneo
- all (all previous together)

```

### Dependencies:

```
https://github.com/sendinblue/APIv3-python-library.git\
```