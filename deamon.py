import daemon
from flathunt import main

with daemon.DaemonContext():
    main()