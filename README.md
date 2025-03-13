# frontdoor route manager
This tool is used to provision front door frontends, routing rules, pools, backends, probes and load balance configs

The input is a path to a config file with a structured yaml scheme
See ./FrontdoorRouteManagerExample.cfg for details


## notes 
azure cli will NOT let you create a backend pool in disabled mode, not sure why it's a true|false option.
when creating backend-pool with --disabled true, it fails will error, BadRequest - All backends are disabled for backend pool
this is a problem because az cli create backend-pool allows only ONE address (backend). So you cannot create
a pool in disabled state. This is very counter intuitive.
You have to create the pool enabled with one backend. The add more backends with update. But in all iterations, there
is no disabled state of the pool. This is not an option in portal either. You can disable probes and backends, but
not backend pools! The --disabled option in az network front-door backend-pool create is a BUG!

