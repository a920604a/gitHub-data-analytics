

- Docker Compose
    - Removed the `image` tag, to replace it with my build from my Dockerfile, as shown
    - Changed `AIRFLOW__CORE__LOAD_EXAMPLES` to false;
    - Removed `redis`, `worker`, `triggerer` and `flower` from the file;
    - Set the CoreExecutor to LocalExecutor.
