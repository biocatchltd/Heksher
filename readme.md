# Heksher
Heksher is a service that makes shared context variables a breeze. It is designed with setting management in mind, but
can be used for any data that needs to be shared and updated throughout an entire architecture.

[Documentation can be found here](https://heksher.readthedocs.io/en/latest/)

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
Currently, Heksher supports the following environment variables:
* `HEKSHER_DB_CONNECTION_STRING`: (required) An [SqlAlchemy-style connection string](https://docs.sqlalchemy.org/en/14/core/engines.html#database-urls)
 that leads to a postgreSql database that has been initialized (Heksher supports alembic to initialize a database).
* `HEKSHER_STARTUP_CONTEXT_FEATURES`: (required) A semicolon-delimited list of context features. Heksher will adapt the
  database's existing context features to this list (or raise an error if it cannot).
* `HEKSHER_LOGSTASH_HOST`, `HEKSHER_LOGSTASH_PORT`, `HEKSHER_LOGSTASH_LEVEL`, `HEKSHER_LOGSTASH_TAGS`: Optional values
  to allow sending logs to a logstash server.
* `DOC_ONLY`: set to "true" to enable doc-only mode, where the service does not actually connect to any sql database
and only the "/redoc" and "/doc" apis function. read more about DOC_ONLY mode in the documentation.

The service itself can be run from the docker image [found in dockerhub](https://hub.docker.com/repository/docker/biocatchltd/heksher).

## Deployment
The service doesn't provide any authorization/authentication as a feature. This is handled on our end by a sidecar. We recommend to use the service only internally, and for external usage use authentication/authorization-supporting API Gateway.

## How do I interface with it?
Heksher supports an HTTP interface. There are many methods that adhere to be REST-ful (and can be viewed in full by
accessing the `/redoc` route), but the two central routes that are not REST-ful are:

