Setting Aliases
=========================

Some settings may need to be renamed. In order to preserve compatibility with past users, these renames are handled
gradually.

Each setting has a list of aliases. Any setting can be referred to by any of its aliases. When a setting is renamed,
it's old name is added to the list of aliases.

For example:

#. A new setting with name "foo" is declared. The setting is now accessible with its canonical name "foo".
#. The setting is renamed to "bar". The setting is now accessible with either name "bar" or "foo". Its canonical name is
   "bar".
#. The setting is renamed to "baz". The setting is now accessible with "baz", "bar" or "foo". Its canonical name is
   "baz".
