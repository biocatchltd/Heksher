Cookbook
===========

Recommended Naming Schema
---------------------------

To accommodate a single Heksher service handling services for multiple domains (teams, products, etc...), we recommend
prefixing all setting names with a domain name, seperated by a dot ".". For example, if a single Heksher service is
handling settings for two products: backend and frontend, in such a way that the settings for backend are not used by
the frontend and vice versa, we would recommend that all settings for backend be prefixed with "backend." and all
settings for frontend be prefixed with "frontend.". This would allow both products to have settings with similar names
with no risk of collision.

These domain prefixes can be nested to create a hierarchy of domains.