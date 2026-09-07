# Installing Gideon Transcribe

This guide is for the IT generalist who will install and look after the app. It does not assume you are a programmer, and it does not ask you to choose between ways of doing anything: each step is one command, or one thing to click, followed by how to check it worked.

The app runs on one server in your office, on Docker, and nothing it does leaves the building. Installing it is about two hours the first time, most of it waiting for downloads. Once it is running, keeping it running is one script, `./transcribe`, and one command to upgrade.

**Nothing is ever pushed from a workstation to the server, and nothing is ever copied over the install folder.** Code reaches the server only by `./transcribe upgrade <tag>`, which fetches a Release from GitHub and checks it out. If you find yourself copying files onto the server by hand, stop: that is not how this app is installed or changed.

## 1. What you need

**A server.** One machine, in your building, that stays on. It needs:

- **One NVIDIA graphics card** with at least **20 GB of video memory to spare** for the transcription service. That figure comes from measuring the service on six hours of real recordings and adding room; it is in the service's own README under "GPU budget". If the AI assistant's engine is to run on the same card, it needs its own memory on top, and `LLM_LOCAL_GPU_FRACTION` in the appendix is how the two share it.
- **Ubuntu Server 24.04 or newer.**
- **The NVIDIA driver.** `nvidia-smi` prints the card and the driver version when it is installed.
- **The NVIDIA container toolkit with CDI turned on**, so Docker can hand the card to a container. `nvidia-ctk cdi list` prints the card when it is right.
- **Docker with the Compose plugin.** `docker compose version` prints a version when it is right. The app needs Compose as a plugin (`docker compose`, with a space), not the older separate `docker-compose`.
- **A data drive**, separate from the drive the operating system is on, and large. Recordings are big: a six-hour body-worn camera export is about 13 GB. The app keeps 200 GB free on this drive by default and pauses uploads when it cannot.
- **An account on the server with `sudo` and in the `docker` group**, for the person installing. This guide calls it the compose admin. It is a separate thing from the `transcribe` account the app runs as, which is made in the server preparation step and is never in the docker group.

**A name and a certificate.** The app answers on one hostname in your office's DNS, over HTTPS, with a certificate from your office's own certificate authority. Section 2 has the request.

**Access to the office directory.** Sign-in is against your Active Directory. Section 2 has the checklist.

**Network access from the server**, at install and upgrade time, to the hosts in the appendix: GitHub for the code, the container registries for the images, Hugging Face for the models. At run time the server talks only to your domain controllers and to itself.

## 2. Before you start

Three things are done away from the server, and each needs somebody with the right permissions. Do them first, so the install itself is not held up.

### The directory checklist

You are making two groups, one read-only account, and one file. Do it by clicking, or with PowerShell; both come to the same thing.

1. **Create the Sign-in group.** Everybody in it may sign in to the app. Nested groups count, so it can hold other groups.
2. **Create an Admin group** if you want Admins to come from the directory. Everybody in it is an Admin of the app. This is optional; an Admin can also be set by hand in the app, and there is always a Local admin.
3. **Create the bind account.** A read-only directory account the app signs in as to look people up. An ordinary domain account is enough: it needs no delegation, no group beyond Domain Users, and no right to see `memberOf`, because the app reads the groups' member lists instead. Set its password never to expire, and write the password down somewhere safe; you will type it once, into `./transcribe install`, and it goes into a file only the app reads.
4. **Export the office CA root as PEM.** The app checks your domain controllers' certificates against it. Take it from any PEM your office already trusts, or export it from any domain-joined machine (see below).
5. The eight `LDAP_*` keys in the appendix are what `./transcribe install` asks you for. Have the group names, the bind account's logon name, and your domain's base DN to hand.
6. When the app is running, **Test directory connection** on its Status page proves the whole chain.

**By clicking**, in Active Directory Users and Computers: New, Group, for each group; New, User, for the bind account, with "Password never expires" ticked and "User cannot change password" ticked; add the first users to the Sign-in group.

**By PowerShell**, on any workstation with the directory tools, run as an account allowed to create objects. Replace the angle-bracket parts, and name one domain controller in `-Server`:

```powershell
New-ADGroup -Name "<Sign-in group>" -GroupScope Global -Path "<OU distinguished name>" -Server <a domain controller> -Credential (Get-Credential)
$password = Read-Host -AsSecureString "Password for the bind account"
New-ADUser -Name "<bind account>" -SamAccountName "<bind account>" -UserPrincipalName "<bind account>@<your domain>" -AccountPassword $password -Enabled $true -PasswordNeverExpires $true -CannotChangePassword $true -ChangePasswordAtLogon $false -Path "<OU distinguished name>" -Server <a domain controller> -Credential (Get-Credential)
Add-ADGroupMember -Identity "<Sign-in group>" -Members <a first user> -Server <a domain controller> -Credential (Get-Credential)
```

Repeat the first line for an Admin group if you want one.

**The CA root as PEM**, from any domain-joined Windows machine:

```powershell
Export-Certificate -Cert (Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -like "*<your CA's name>*") -FilePath office-root.cer
certutil -encode office-root.cer office-root.pem
```

Three warnings:

- **Give the other domain controllers a minute** after creating the objects before you test anything. Replication is not instant.
- **Never test the bind with a wrong password against the real account.** A domain lockout policy can lock it after a few wrong tries, for a period, and then nobody can sign in to the app.
- **A blank password may be accepted as an anonymous bind**, so a test that "passes" with an empty password proves nothing. Test with the real one.

### The certificate request

The app's certificate comes from your office CA, on the Web Server template, for the app's hostname. The key is made on the server and never leaves it.

1. **On the server**, make the key and the request. Replace `<hostname>` with the app's full name, the one people will type:

    ```bash
    openssl req -new -newkey rsa:3072 -nodes -keyout key.pem -out <hostname>.csr -subj "/CN=<hostname>" -addext "subjectAltName=DNS:<hostname>"
    ```

2. **Copy the `.csr` to a Windows machine** and submit it as an account with Enroll on the Web Server template. The CA config string is what `certutil -dump` on that machine calls "Config":

    ```
    certreq -submit -attrib "CertificateTemplate:WebServer" -config "<CA config string>" <hostname>.csr <hostname>.cer
    ```

3. **Copy the `.cer` back to the server exactly as it is**, to a staging folder for now. It is already PEM: `certreq` answers a PEM request with a PEM certificate. Do not run it through `certutil -encode`, which would encode it twice; this has happened.
4. **Check it** on the server, with the CA root from the directory checklist beside it:

    ```bash
    openssl verify -CAfile office-root.pem <hostname>.cer
    ```

    and confirm the certificate and the key belong together by comparing their public keys:

    ```bash
    diff <(openssl x509 -in <hostname>.cer -pubkey -noout) <(openssl pkey -in key.pem -pubout)
    ```

    No output from `diff` means they match.

5. **Create the DNS record for the hostname now**, pointing at the server's LAN address, before anybody tries the name. The zone lives on your domain controllers, and a caching resolver in front of them remembers "that name does not exist" for the zone's negative TTL, usually an hour. A name that is looked up before it exists goes on failing for that long.

### The Hugging Face account and token

The speaker-separation model is downloaded once, by the server, from Hugging Face, and it is behind a gate: somebody has to accept its conditions before it can be fetched.

1. **The account must be a user account**, not an organisation. Acceptance is granted to individuals. An office is better served by a shared account that outlives one person, with its password kept where the office keeps such things.
2. **Accept the conditions** of the model named in the service's README. The gate's form asks for a company or university and a use case whose options are all commercial; "Other" is the honest answer.
3. **Make a token** for that account: a plain Read token, or a fine-grained one with "Read access to contents of all public gated repos you can access" ticked.
4. **Both are needed.** A token from an account that has not accepted is refused, and acceptance without a token cannot download anything.
5. Each office accepts the licence itself. The model is never redistributed with the app.

You will type the token once, into `./transcribe install`. Nothing is shown as you type, and it goes into a file only the service reads.

## 3. Install

### Step 1: prepare the server

One `sudo` session, as the compose admin. Replace `<App data folder>` with a folder on the data drive, for example `/data/transcribe`, and `<Install home>` with where the code will live, for example `/opt/gideon-transcribe`.

```bash
sudo useradd --system --no-create-home --home-dir <App data folder> --shell /usr/sbin/nologin --user-group transcribe
```

```bash
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>
```

```bash
sudo install -d -o $USER -g $USER -m 0755 <Install home>
```

What that did: made a system account called `transcribe` that cannot log in and is not in the docker group, which is the account every part of the app runs as; made the one folder that will hold everything the app stores, owned by that account; and made an empty install folder owned by you. The app makes its own sub-folders inside the data folder when it starts.

Check:

```bash
id transcribe && sudo ls -la <App data folder>
```

`id` prints the account with its numbers; `ls` shows the folder empty and owned by `transcribe`.

### Step 2: clone a Release

Git refuses to clone into a folder that already has files in it, which is why the install home is made empty and why the certificate goes in afterwards. Pick the newest Release from the repository's Releases page; its tag looks like `v1.2.0`.

```bash
cd <Install home> && git clone --branch <tag> https://github.com/TNMD-FDO/gideon-transcribe.git .
```

Check: `ls` shows `transcribe`, `compose.yaml`, `app/`, and the rest.

### Step 3: place the certificate

From the staging folder where the certificate waited:

```bash
mkdir -p tls ca && mv <staging>/<hostname>.cer tls/cert.pem && mv <staging>/key.pem tls/key.pem && mv <staging>/office-root.pem ca/office-root.pem && chmod 600 tls/key.pem && rmdir <staging>
```

Check: `ls -l tls ca` shows the three files, the key readable only by you.

### Step 4: run the install

```bash
./transcribe install
```

It first checks what the server has: Docker, the Compose plugin, the NVIDIA driver, and the `transcribe` account. If one is missing it says which, and stops.

Then it asks, in plain words, for the facts about your office, offering a sensible default where there is one:

- whether directory sign-in is on, and if so the directory's address, the bind account and its password, the base DN, and the two groups;
- the address people will type, the port, the server's LAN address to listen on, and which networks may connect;
- the App data folder and the time zone;
- which graphics card the transcription service should use, chosen from a list by its UUID rather than its number, because numbers move between reboots;
- the Hugging Face token;
- the AI assistant's engine, if your office runs one: the Docker network a vLLM listens on, and its token. Leave the network blank for none. The engine's address and served model name are entered in the Admin panel afterwards, where Test connection proves them. `./transcribe engine` asks these again on its own. An office with no engine of its own can start the Local engine instead, after the install: see "The Local engine" below.

Nothing you type leaves the server, and none of it is ever committed to the repository. The random secrets the app needs, the database password and the like, it makes itself; nobody types them.

It writes two environment files, `.env` here and `whisperx-service/.env`, and the secret files under `secrets/` and `whisperx-service/secrets/`. Then it prints what is left, in order, which is Step 5.

If you run it a second time it refuses to overwrite anything. `./transcribe install --reconfigure` is how you change the office facts later, and `./transcribe directory` changes only the directory ones.

### Step 5: bring it up

The things install printed, in order. Each is one command, run from the install home.

**Get the images.** Compose pulls the app's two images from the registry, and the upstream ones (the database, the web server, the upload sidecar):

```bash
docker compose pull
```

If the registry cannot be reached from your server, or nothing is published there yet, build the two images on the server instead. It takes ten to twenty minutes the first time and is mostly waiting:

```bash
docker compose build
```

**Fetch the models.** About 6 GB, once, into the App data folder. This is the step that needs the Hugging Face token:

```bash
docker compose run --rm whisperx pull
```

**Start everything:**

```bash
docker compose up -d
```

**Make the Local admin.** An Admin account kept inside the app, for reaching the Admin panel when the directory is down. Give it a long password and keep that where the office keeps such things:

```bash
docker compose run --rm app create-local-admin
```

**Check it all:**

```bash
./transcribe check
```

Section 4 says what each line of that means. When every line passes, the app is installed.

### The fast lane

A second copy of the transcription service for what must not wait behind a long job: a recording made in the app, and later the interpreter. The install asks whether to turn it on; the answer is no unless you say yes, and nothing is lost without it but the waiting. It needs about eight gigabytes of the card's memory. Later, or to change your mind:

```bash
./transcribe fast-lane on
```

```bash
./transcribe fast-lane off
```

The admin guide's "The fast lane" section says what it does and what the Status page shows.

### The Local engine

The AI assistant needs a language-model engine. If your office already runs a vLLM, `./transcribe engine` points the app at it. If not, the stack can run a small one itself, on the same card as the transcription service, within a share of that card's memory:

```bash
./transcribe engine local on
```

It shows the cards on the server and asks three things, each with a sensible answer already filled in: which card (by UUID; it offers the one with the least in use, which is the transcription service's), which model (the default is `Qwen/Qwen3.5-4B`, chosen in `docs/research/local-engine-model.md` because it fits in 20 GB with its cache for a six-hour transcript), and what share of the card's memory the engine may take (0.21 of a 96 GB card is 20 GB). It writes a token for the engine if none is stored, starts it, and points the Admin panel's Engine address and Model name at it. The first start downloads the model's weights into the app data folder (about 8 GB for the default) and takes some minutes; `./transcribe logs vllm` shows the progress, and `./transcribe check` says when it is healthy. Then, on the Panel's Status page, press **Test connection**; when it answers "ready", turn the **AI assistant** toggle on.

```bash
./transcribe engine local off
```

stops the engine, frees the card, and leaves the app using no engine: the panel's Engine address and Model name are cleared and the AI assistant toggle is turned off, so nobody sees a button for an engine that is not there and the Status page reads "off; no engine is configured". The weights stay on disk for the next `on`; delete `<App data folder>/models/vllm` to free the space. Switching to a shared engine is `./transcribe engine` as above: it asks for the engine's address and model name and writes them into the panel, and it stops a running Local engine in the same step, since the two are never on together.

### The backup

`./transcribe install` asks for the backup target and the Operator address after the engine. With a target named it makes the store account's key when there is none and prints the public half to paste into the store, generates the repository password, records the store's host key and prints its fingerprint to compare, makes the repository on the store, and writes the three host timers. The admin guide's Backups chapter has the store's side, in order, and what goes into the password manager before the first copy. Then, with the stack up:

```bash
./transcribe backup
```

```bash
./transcribe restore-drill
```

Leave the target empty to run without backups; the Status page says so in red until one is set with `./transcribe install-backup`.

### The mail

After the backup, `./transcribe install` asks four plain questions: the relay's host and port; whether it needs a sign-in (then the name, and the password typed hidden into `secrets/smtp_password`); the sender address; and the Operator address. The relay is your office's own mail relay; it must accept mail from the server's address and let the sender address through, which `./transcribe check` proves by sending one test message to the Operator address. Before the install, fill the `mail` attribute for every member of the Sign-in group in the directory: that is the only place the app reads an email address from, and `check` counts who still lacks one.

Leave the relay empty to run without mail. The install says what that loses: no retention digest, no other notification, and no Operator mail; the app's pages show everything a message would say. `./transcribe install-mail` asks the questions again later.

## 4. Check

`./transcribe check` runs every smoke check and prints a plain report. Run it whenever something seems wrong; it never changes anything. Each line is `pass`, `amber`, or `FAIL`, and a failure says what to do.

**The server**

| Line | What it means |
|---|---|
| the transcribe account exists and is not in the docker group | The account the app runs as is there, and cannot control Docker. |
| the app data folder is transcribe's, mode 750 | The one folder that holds everything is owned by the app and private. |
| scratch/, cases/, uploads/ are transcribe's | The sub-folders the web server is handed read-only are owned by the app, so it can write into them. |
| the checkout is at the release tag vX.Y.Z | The code is a Release, not somebody's edits. "not at a release tag" means the install did not follow this guide. |
| the disk has N GB free | Free space on the data drive. Amber under the minimum the app keeps. |

**The name and the certificate**

| Line | What it means |
|---|---|
| hostname resolves | DNS answers for the app's name. |
| the certificate is good until DATE | Its expiry. Amber within a month; the admin guide has the renewal. |
| the certificate names hostname | The certificate is for the right name. |

**The containers**

| Line | What it means |
|---|---|
| every container is running | All seven parts are up and healthy. A failure names the one that is not; `./transcribe logs <name>` shows why. |

**The directory**

| Line | What it means |
|---|---|
| Bind as the bind account | The app can sign in to the directory. |
| Read the Sign-in group: N member(s) | It can see who may sign in. Zero members means nobody can. |
| Read the Admin group: N member(s) | The same for Admins. |
| Resolve a member of the Sign-in group | It can turn a member into a person with a name and address. |
| Find that member under the search base | The base DN is right. |
| The nested rule on the Sign-in group | Groups inside the group count, as they should. |

**The WhisperX service**

| Line | What it means |
|---|---|
| the service answers | The transcription service is up, has its models, and can see the card. |

**Email**

| Line | What it means |
|---|---|
| the relay HOST accepted a test message to ADDRESS: REPLY | One message went through to the Operator address; the relay takes mail from this server and lets the sender through. A failure names the reason. |
| every one of the Sign-in group's N members has a mail value | Everybody who may sign in can be mailed. Amber names who cannot; fix it in the directory. |
| note SMTP_HOST is empty, so the app sends no mail | Mail is off; nothing else is checked. |

The last line is either `Everything checked passed.` or a count of what did not.

## 5. First sign-in

1. **Open the address** in a browser on an office computer: `https://<hostname>:<port>/`. The port is 8443 unless you changed it. The sign-in page appears with no certificate warning; a warning means the CA root is not trusted by that computer, which is a workstation matter and not the server's.
2. **Sign in as the Local admin** you made. You land on the Upload page. **Panel** at the top opens the Admin panel; its **Status** page should be green all the way down. **Test directory connection** on that page runs the directory checks from inside the app.
3. **Sign out and sign in as an ordinary user**: somebody in the Sign-in group who is not in the Admin group. This matters, because it is the only way to see that ordinary sign-in works and that a user sees no Panel link. If you have no such person yet, add one to the group for the test.
4. **Upload one recording** as that user, a short one, and watch it through: the Batch page shows it uploading, prepared, in line, transcribing, and done. Open it in the viewer, play it, and download the transcript. That is the whole app, once round.
5. Sign out. The dialog says the recording will go, and it does. That is by design: nothing a user does not put in a case outlives their session.

## 6. When it fails

| What you see | What it means | What to do |
|---|---|---|
| `there is no transcribe account; the install guide's server preparation makes it` | Step 1 was skipped. | Run the `useradd` in Step 1, then `./transcribe install` again. |
| `nvidia-smi is not on this server, so no GPU can be reserved` | The NVIDIA driver is not installed, or the machine has not been rebooted since. | Install the driver, reboot, and check `nvidia-smi` prints the card. |
| `There is already a .env here.` | `install` was run before. | It will not overwrite anything. `./transcribe install --reconfigure` changes the office facts; `./transcribe directory` changes only the directory. |
| `There is no Hugging Face token stored; the model pull will refuse.` | The token step was skipped, or Enter was pressed with nothing stored. | `./transcribe install --reconfigure` and type the token when asked. |
| `There is no Docker network called '...' on this server.` | The engine's network was mistyped, or the engine's own stack is not running. | `docker network ls` lists them; start the engine's stack first, then `./transcribe engine`. |
| `The AI assistant refused the connection. Ask IT.` (in the app) | The engine wants a different token from the one in `secrets/llm_api_token`, or the file is empty. | `./transcribe engine`, paste the engine's token, then `docker compose up -d`. |
| The Status page says `AI assistant: unreachable since ...` | The engine is down, or `llm-worker` is not on its network. | Check the engine's own stack; `./transcribe check` proves the network membership; `./transcribe engine` fixes it. For the Local engine, `./transcribe logs vllm`: the first start downloads the model and takes minutes. |
| `the engine token file is empty` in `./transcribe logs vllm` | The Local engine refuses to start without a token. | `./transcribe engine local on` writes one when the file is empty. |
| `error from registry: denied` during a pull | The two images are not published, or the server is not signed in to the registry. | Nothing. Compose falls back to building them on the server, which is slower and otherwise the same. |
| `The registry had nothing to give, so the images are built here.` | As above, during an upgrade. Not an error. | Wait. Ten to twenty minutes the first time. |
| `The build failed, so the upgrade stops here.` | Building an image on the server failed. The old containers are still running. | Read the message above it. Usually the server cannot reach one of the appendix's hosts. `./transcribe rollback <the tag you were on>` puts the checkout back. |
| `There is no release called vX.Y.Z.` | The tag does not exist, or the server cannot reach GitHub. | Check the tag on the Releases page, and that `github.com` is reachable from the server. |
| `... is not the build the release recorded` | The registry served an image whose identity differs from the one the Release was built as. Nothing was started. | Do not ignore it. `./transcribe upgrade <tag> --build` builds from the Release's own source instead. Tell whoever looks after the repository. |
| `This release carries no digest record` | The Release's workflow has not finished publishing yet, or the Release is from before v1.0.0. | Not an error. Wait for the Release to appear on GitHub and upgrade again, or go on if you are content with the pull. |
| `A job is running. An upgrade restarts the app, so wait for it.` | Somebody's transcription is in progress. | Wait for it. The Queue page in the panel shows what is running. |
| The upgrade ends without a word after "the checkout is at ...", and `./transcribe status` still shows the old release's images | The checked-out script stopped part way (a v1.2.1 script did this on a "Permission denied" it could not report). The checkout moved and nothing was rebuilt. | `git fetch --tags && git checkout <the tag you want>`, then `./transcribe upgrade <the same tag>`. The upgrade is safe to run twice. |
| `There are local edits to tracked files here.` | Somebody changed a file in the install home by hand. | `git status` in the install home shows which. Nothing office-specific belongs in a tracked file; it belongs in `.env`. Put the edit somewhere else, then upgrade again. |
| Compose says `is a directory` and nothing else | `COMPOSE_FILE=` is in `.env` with nothing after it. | Delete that line, or put a `#` in front of it. It must be left out entirely, not set empty. |
| `hostname does not resolve` | The DNS record is missing, or was looked up before it existed and the negative answer is cached. | Create the record; flush the resolver's cache, or wait up to an hour. |
| `Bind as the bind account` fails | The bind account's name or password is wrong, or the CA root does not match the domain controllers' certificates. | Do not keep trying passwords; the domain may lock the account. Check `LDAP_CA_FILE` is the right root, then `./transcribe directory`. |
| `Read the Sign-in group: 0 member(s)` | The group is empty, or the DN is wrong. | Add a member in the directory; check the DN against `.env`. |
| `the service did not answer` | The transcription service is down. | `./transcribe logs whisperx`. The usual causes: the models were not pulled (`docker compose run --rm whisperx pull`), or the card's UUID in `whisperx-service/.env` is wrong (`nvidia-smi -L` lists them). |
| The Installation page says the release is `not tagged` | The server is running code that was not installed by `./transcribe upgrade`. | `./transcribe upgrade <the newest tag>`. |
| Uploading is paused because the server is low on space | Free space on the data drive is under the minimum the app keeps. | Free space, or have users clear finished batches. The minimum is a setting on the panel's Limits page. |

## 7. Upgrade

Upgrades come as Releases on GitHub. The app never checks for them and never phones home, so somebody has to hear about them: on the repository's page, **Watch**, **Custom**, **Releases**, and GitHub emails you when one is published.

Each Release's notes open with two fixed lines, and you read them before you do anything:

```
Models: unchanged
Database: migrates
```

`Models: changed` means the upgrade fetches models again, which takes a while. `Database: migrates` means the database changes when the app starts; it does that on its own, and there is no separate step.

Then, from the install home, with nobody's transcription running:

```bash
./transcribe upgrade <tag>
```

It refuses if a job is running or if a tracked file has been edited by hand. Then it takes a dump of the database and a copy of your configuration into the backup folder under the App data folder, fetches the tag and checks it out, reads the two lines out to you, pulls the images (or builds them if the registry has nothing), starts everything, restarts the web server so it re-reads its configuration, fetches models if the Release said to, and ends with `./transcribe check`.

When it pulls, it also checks that what arrived is what the Release was built as. Every Release from v1.0.0 records the exact identity of its two images, and the upgrade compares the pulled images against that record before it starts anything. A mismatch stops the upgrade and prints both identities; the way on is `./transcribe upgrade <tag> --build`, which builds from the Release's own source instead of trusting the registry. A Release with no record, which is every one before v1.0.0, is said so, and the upgrade goes on.

**Nothing is ever pushed from a workstation to the server, and nothing is ever copied over the install folder.** This command is the only way code reaches the server.

## 8. Roll back

If a Release is wrong for you, go back to the one before:

```bash
./transcribe rollback <the tag you were on>
```

It checks that tag out and starts it. Run without a tag, it lists the tags this server knows about.

Rolling back the code does not roll back the database. Usually that does not matter, because the old code reads the new database happily. When it does matter, the app will not start after the rollback, and the fix is the dump the upgrade took before it changed anything:

```bash
./transcribe restore-dump <App data folder>/backup/pre-<the tag you left>.dump
```

It asks you to type `yes`, because it replaces everything in the database with what is in that file, and then starts everything again.

## 9. Uninstall

Nothing was installed outside the install home and the App data folder, and no system services were added: Docker's own restart policy is what brings the app back after a reboot.

Stop and remove the containers and their networks, from the install home:

```bash
docker compose down
```

Remove the data, if you mean to. This is the database, every recording, every case, the models, and the backups. There is no way back from it:

```bash
sudo rm -rf <App data folder>
```

Remove the code and the configuration:

```bash
sudo rm -rf <Install home>
```

Remove the account:

```bash
sudo userdel transcribe
```

The directory objects from Section 2 and the certificate are yours to remove or keep.

## 10. Appendix

### Every environment key

`.env` in the install home, written by `./transcribe install`. The example beside it, `.env.example`, has the same keys with a comment above each; it is the only environment file in the repository. Nothing here is ever committed.

**The address, and who may reach it**

| Key | Meaning |
|---|---|
| `APP_HOSTNAME` | The app's name in your DNS, which is also the name on its certificate. |
| `HTTPS_PORT` | The port it answers on. 8443 by default, so it can share a server with something on 443. |
| `BIND_ADDRESS` | The server address the port is published on. The LAN address keeps it off other interfaces the machine has. |
| `ALLOWED_CLIENT_CIDRS` | The client networks allowed in, separated by spaces. Everyone else gets 403 with no page. |

**The folder and the account**

| Key | Meaning |
|---|---|
| `APP_DATA_DIR` | The App data folder: uploads, working files, the database, the models, the service's state, and the backups. On the data drive. |
| `APP_UID`, `APP_GID` | The `transcribe` account's numbers, from `id transcribe`. Every part of the app runs as this account. |
| `TZ` | The office time zone, so schedules run at office-local times. The host stays on UTC. |

**The database**

| Key | Meaning |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER` | The database's name and the account that made it. |

**Secret files.** Each holds one secret and nothing else. The install makes the random ones and asks for the ones a person holds.

| Key | Meaning |
|---|---|
| `DJANGO_SECRET_KEY_FILE` | The app's own signing key. Random, generated at install. |
| `POSTGRES_PASSWORD_FILE` | The database password. Random, generated at install. |
| `WHISPERX_TOKEN_FILE` | The token the app presents to the transcription service. Generated at install. |
| `LDAP_BIND_PASSWORD_FILE` | The bind account's password, typed at install. |
| `LLM_API_TOKEN_FILE` | The AI assistant's engine token. |

**The transcription service**

| Key | Meaning |
|---|---|
| `WHISPERX_URL` | Where the service answers, on its own Docker network. It publishes no port and has no hostname. |
| `WHISPERX_FAST_URL` | The fast lane's address, `http://whisperx-fast:8000` while it is on, empty otherwise. `./transcribe fast-lane on` and `off` write it. |

**The office directory.** Set at install, shown read-only in the panel, never edited there.

| Key | Meaning |
|---|---|
| `LDAP_ENABLED` | `true` for directory sign-in; `false` for an evaluation with Local admins only. |
| `LDAP_SERVER_URI` | The directory by domain name over LDAPS, `ldaps://<your domain>:636`, never one controller. |
| `LDAP_CA_FILE` | The office CA root as PEM, `./ca/office-root.pem`. Empty means the system trust store, for an office whose certificates come from a public authority. |
| `LDAP_BIND_USER` | The bind account's User logon name. |
| `LDAP_SEARCH_BASE` | The domain's base DN, under which people are found. |
| `LDAP_SIGNIN_GROUP` | The Sign-in group's full DN. Membership, nested or direct, grants sign-in. |
| `LDAP_ADMIN_GROUP` | The Admin group's full DN, or blank for no group-held Admins. |

**Running**

| Key | Meaning |
|---|---|
| `LOG_LEVEL` | `INFO` says what happened, to which id, and how long it took. It never prints transcript text, file names, or anything a user typed. |
| `MEDIA_THREADS_PER_JOB` | How many processor threads one piece of media work may use. Media work never uses the card. |
| `MEDIA_CONCURRENT_JOBS` | How many pieces of media work run at once. These two are how you keep some of the server for everything else. |
| `RELEASE_TAG` | The Release this server is running. Written by `./transcribe upgrade`, never by hand. Empty on a first install. |

**The AI assistant's engine.** The assistant talks to a language-model engine that is either one your office already runs or one this stack starts. Without either, the assistant stays off and everything else works.

| Key | Meaning |
|---|---|
| `LLM_NETWORK` | The Docker network the engine is reached on. |
| `BACKUP_TARGET` | The backup store, as `sftp:<account>@<store>:/<folder>`; empty means backups are off. The admin guide's Backups chapter has the store's side. |
| `BACKUP_SSH_KEY_FILE`, `BACKUP_KEY_FILE`, `BACKUP_KNOWN_HOSTS_FILE` | The store account's private key, the repository password, and the store's host key, each a file under `secrets/`. The first two never ride in a backup: a fresh server gets them from the office's password manager. |
| `BACKUP_KEEP_DAYS`, `BACKUP_LOCAL_DUMPS` | Nightly copies kept on the store (30) and dumps kept on the server (7). |
| `BACKUP_TIME`, `DRILL_TIME` | When the nightly backup runs (02:00) and when the weekly check and the monthly drill run (04:00, Sundays). Written into the host's timers; after a change, `./transcribe install-timers`. |
| `OPERATOR_EMAIL` | The Operator address: the backup reports, each night the cases whose owner has left, the test message, and the Reply-To on every message; empty means no Operator mail. |
| `SMTP_HOST`, `SMTP_PORT` | The office's mail relay and its port (25). An empty host means the app sends no mail at all. |
| `SMTP_STARTTLS` | `auto` (upgrade to TLS when the relay offers it, require it when a password is set), `always`, or `never`. |
| `SMTP_USER`, `SMTP_PASSWORD_FILE` | The relay's sign-in, only when it wants one; the password lives in `secrets/smtp_password`, written by the install. |
| `MAIL_FROM` | The sender, shown as "Gideon Transcribe <address>". Required when `SMTP_HOST` is set. |
| `COMPOSE_FILE` | Which compose files Compose reads. Left out entirely for most offices; uncommented only for a shared engine. Never set empty: Compose reads an empty value as a path and refuses to start. |
| `COMPOSE_PROFILES` | `llm` starts the Local engine in this stack; `./transcribe engine local on` sets it and `off` clears it. Empty means a shared engine, or none. |
| `LLM_LOCAL_MODEL` | The model the Local engine loads, as Hugging Face names it. Default `Qwen/Qwen3.5-4B`, which fits in 20 GB with its cache. |
| `LLM_LOCAL_GPU_UUID` | Which card the Local engine uses, by UUID; `engine local on` asks and offers the least busy one. |
| `LLM_LOCAL_GPU_FRACTION` | The share of that card's memory the engine may take, leaving the rest for transcription. Default 0.21, which is 20 GB of a 96 GB card. |

### The files beside the keys

All in the install home and all ignored by git, so none of them is ever committed:

| File | What it is |
|---|---|
| `whisperx-service/.env` | The transcription service's own settings, written by `./transcribe install`. |
| `whisperx-service/secrets/` | The service's tokens file and the Hugging Face token. |
| `secrets/` | The app's secret files named above. |
| `tls/cert.pem`, `tls/key.pem` | The certificate and its key, the key mode 0600. |
| `ca/office-root.pem` | The office CA root as PEM. |

And under the App data folder, `backup/`, where `./transcribe upgrade` puts the database dump and the configuration copy it takes before every upgrade, and `./transcribe backup-db` puts a dump on demand.

### The hosts the server must reach

At install and upgrade only:

| Host | For |
|---|---|
| `github.com` | the clone and the fetch |
| `ghcr.io` and `pkg-containers.githubusercontent.com` | the app's two prebuilt images |
| `registry-1.docker.io` and `production.cloudflare.docker.com` | the upstream images: the database, the web server, the upload sidecar |
| `huggingface.co` and `*.hf.co` | the models; `*.hf.co` covers the download hosts, which Hugging Face changes without notice |
| `pypi.org`, `files.pythonhosted.org`, `download.pytorch.org`, `deb.debian.org` | only when an image is built on the server rather than pulled |

At run time: your domain controllers on the LAN, the mail relay on `SMTP_PORT` when one is named, the backup store over SFTP when one is named, and the engine's network inside Docker. Nothing phones home, and the app never checks for updates.
