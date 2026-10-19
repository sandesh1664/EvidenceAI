FROM caddy@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f
# Listen above 1024. Remove upstream bind capability so cap_drop:ALL remains executable.
RUN setcap -r /usr/bin/caddy && chown -R 10001:10001 /data /config
USER 10001:10001
