# Heksher
Heksher is a service that makes shared context variables a breeze. It is designed with setting management in mind, but
can be used for any data that needs to be shared and updated throughout an entire architecture.

## How does it work?
Heksher stores a collection of settings, these are the context variables. For each setting, there is a set of rules,
each rule has a value and a set of conditions. These conditions are set by each context inside process individually.
So that whenever a context needs to know the value to use for each setting, it can just filter through the rules. 

### Example
Assume we have 3 context features: `account`, `user`, and `theme`. We also have a setting called `cache_size` of type
`int`. We might have a ruleset that looks like this (conceptually, the data is stored differently):

|account|user|theme|value
|:---:|:---:|:---:|:---:
|john|*|*|100
|jim|*|*|50
|jim|admin|*|200
|*|guest|*|10
|*|guest|dark|20

Note that the rules are prioritized by last-feature first, and wildcards are prioritized last, so this rule set
evaluates to:
1. If the user is `guest`, using the `dark` theme, return 20.
1. Otherwise, if the user is `guest` (without the `dark` theme, since in that case we will have returned 20 already),
  return 10.
1. Otherwise, if the account is `jim`, with the `admin` user, return 200.
1. Otherwise, if the account is `jim`, return 50.
1. Otherwise, if the account is `john`, return 100.
1. Otherwise, return the client-specific default value (defined when a client declares the setting)

Now if one of our servers is handling a request from a specific user, using a specific account, with a specific theme,
we can find out the value of `cache_size` by simply querying the Heksher service with those context feature values.
(it is recommended to query and cache the results in advance, see below).

## How do I make it work?
Currently, Heksher supports two environment variables, both of which are required:
* `HEKSHER_DB_CONNECTION_STRING`: An [SqlAlchemy-style connection string](https://docs.sqlalchemy.org/en/14/core/engines.html#database-urls)
 that leads to a postgreSql database that has been initialized (Heksher supports alembic to initialize a database).
* `HEKSHER_STARTUP_CONTEXT_FEATURES`: A semicolon-delimited list of context features. Heksher will adapt the database's
  existing context features to this list (or raise an error if it cannot).

The service itself can be run from the docker image `<TBD>`.

## How to I interface with it?
Heksher supports an HTTP interface. There are many methods that adhere to be REST-ful (and can be viewed in full by
accessing the `/redoc` route), but the two central routes that are not REST-ful are:

### PUT `/api/v1/settings/declare`
declare that a setting exists, and create it if it doesn't.

arguments:
* name: the name of the setting.
* configurable_features: the names of the context features that are allowed to configure this setting (list[str]).
* type: the type of the setting.
* default_value: optional. default value of the setting.
* metadata: optional. additional metadata.

output:
* created: bool, whether the setting was created or it already existed.
* rewritten: list of strings, containing whichever elements of any previous declaration was overwritten (if the setting 
  did not exist before the call, this list is empty)
* incomplete: a mapping of fields that were declared with incomplete data, with the complete data (which remains 
  unchanged)
  
### GET `/api/v1/rules/query`
Get a set of relevant rules.

arguments:
* setting_names: a list of setting names to retrieve (List[str])
* context_features_options: a mapping of context features to lists of values, storing whichever context feature values to return (dict[str,List[str]]).
* cache_time: optional. If provided, all settings that have been unedited since this time are ignored.
* include_metadata: optional boolean (default False). If true, all rules are also provided with their metadata.

output:
* rules: A dict, mapping each setting to a list of dicts, each dict representing a rule, having the keys:
    * value
    * context_features
    * metadata. only present if “include_metadata” is true.

Clients should use this route at regular intervals, updating the rules for each service, to be queried in real-time from
within the client's memory. Clients are encourage to store the rules in a nested mapping, the rules for `cache_size` in
the above example will be stored as:

```json
{
  "john": {
    "*": {
      "*":100
    }
  },
  "jim": {
    "admin": {
      "*": 200
    },
    "*": {
      "*": 50
    }
  },
  "*": {
    "guest": {
      "dark": 20,
      "*": 10
    }
  }
}
```