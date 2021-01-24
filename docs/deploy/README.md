# Deployment
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Turpis egestas pretium aenean pharetra. Orci eu lobortis elementum nibh tellus molestie. Vulputate dignissim suspendisse in est. Vel pharetra vel turpis nunc.

## Extraction
Using the [data extraction](/elt/?id=extract) scripts, there are two separte docker images that run the extractions, hence the next two sections.

**WIP IN PROGRESS - UNPUBLISHED Docker test images**

### Caselaw
Docker needs to access files from the root and `data_extraction` during the building process. Due to access restrictions, the following commands need to be ran from the **root path** (eg `case-law-explorer/`)!

1. Build the image that runs the Rechtspraak and Legal Intelligence extraction scripts
    ```bash
    docker build -t test -f data_extraction/caselaw/Dockerfile .
    ```
2. Run the image that extracts the RS archive, RS metadata and LI metadata in *FOLDER OR S3 BUCKET???*
   ```bash
   docker run \
       -e SAMPLE_TEST="TRUE" \
       -e CLIENT_ID="email" \
       -e CLIENT_SECRET="secret" \
       test  
   ``` 
   Use the following environment variables: 
    - `CLIENT_ID` is the Legal Intelligence API email address
    - `CLIENT_SECRET` is the Legal Intelligence API generated secret token
    - `SAMPLE_TEST` to extract only a Rechtspraak sample dataset (~ 1k cases).

### Citations

WIP