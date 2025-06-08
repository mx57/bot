# Database Setup: PostgreSQL + TimescaleDB

This document provides instructions for setting up a PostgreSQL database with the TimescaleDB extension using Docker. This setup is suitable for local development and testing.

## Prerequisites

*   **Docker:** Ensure Docker is installed and running on your system. You can download it from [the Docker website](https://www.docker.com/get-started).

## 1. Pull TimescaleDB Docker Image

TimescaleDB provides Docker images that come with PostgreSQL and the TimescaleDB extension pre-installed.

Open your terminal or command prompt and run:

```bash
docker pull timescale/timescaledb:latest-pg14
```
*(Note: `latest-pg14` refers to the latest TimescaleDB version compatible with PostgreSQL 14. You can check the [TimescaleDB Docker Hub page](https://hub.docker.com/r/timescale/timescaledb/) for other available tags if needed.)*

## 2. Run TimescaleDB Container

Now, run the Docker container. This command will start a TimescaleDB instance, map the default PostgreSQL port (5432) to your host machine, and set a default password for the `postgres` user.

```bash
docker run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=yoursecurepassword timescale/timescaledb:latest-pg14
```

*   `-d`: Runs the container in detached mode (in the background).
*   `--name timescaledb`: Assigns a name to your container for easy reference.
*   `-p 5432:5432`: Maps port 5432 on your host to port 5432 in the container.
*   `-e POSTGRES_PASSWORD=yoursecurepassword`: Sets the password for the default `postgres` superuser. **Change `yoursecurepassword` to a strong password of your choice.**
*   To persist data across container restarts, you should use Docker volumes. For example:
    ```bash
    docker volume create timescaledb_data
    docker run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=yoursecurepassword -v timescaledb_data:/var/lib/postgresql/data timescale/timescaledb:latest-pg14
    ```

## 3. Connect to the Database

You can connect to the running TimescaleDB instance using any standard PostgreSQL client, such as `psql` (command-line) or GUI tools like DBeaver, pgAdmin, or DataGrip.

**Connection Parameters:**
*   **Host:** `localhost` (or the IP of your Docker host if not local)
*   **Port:** `5432`
*   **User:** `postgres`
*   **Password:** The password you set in the `docker run` command (e.g., `yoursecurepassword`).
*   **Database Name (default):** `postgres` (you can create a new one).

**Using `psql` (from within the container or if `psql` is installed locally):**

To connect using `psql` from your host machine (if installed):
```bash
psql -h localhost -U postgres
```
It will prompt for the password.

Alternatively, you can execute `psql` inside the running Docker container:
```bash
docker exec -it timescaledb psql -U postgres
```

## 4. Create a New Database (Recommended)

It's good practice to create a dedicated database for your application.

Connect using `psql` as shown above, then run:

```sql
CREATE DATABASE crypto_data;
```

You can then connect directly to this new database:
*   Using `psql`: Disconnect (`\q`) and reconnect with `psql -h localhost -U postgres -d crypto_data`.
*   Or, if already connected to the `postgres` database, switch connection in `psql`: `\c crypto_data`

## 5. Enable TimescaleDB Extension

Once connected to your desired database (e.g., `crypto_data`), you need to enable the TimescaleDB extension.

Run the following SQL command:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
```
*(The `CASCADE` option automatically installs any other extensions that `timescaledb` depends on, like ` મતtimescaledb_toolkit` if available and compatible.)*

You should see a confirmation message like `CREATE EXTENSION`.

## Next Steps

Your TimescaleDB instance is now ready. You can proceed to define your schema (see `sql/schema.sql`) and integrate it with the application scripts.

## Managing the Container

*   **Stop the container:** `docker stop timescaledb`
*   **Start the container:** `docker start timescaledb`
*   **View logs:** `docker logs timescaledb`
*   **Remove the container (if you want to start fresh, data will be lost unless using a volume):**
    ```bash
    docker stop timescaledb
    docker rm timescaledb
    # If you used a volume and want to remove it too:
    # docker volume rm timescaledb_data
    ```
