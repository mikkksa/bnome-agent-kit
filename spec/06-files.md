# Files

One store per system. What the owner uploads, what the AI makes, what a client sends
through a program, what the programs and the agents produce — all in folders, all in one
place.

**Reading is the same path everywhere.** Every program of the system, and the system's
agent, see the store at `/files`, read-only: `/files/Price list.xlsx` is the same file
in all of them. Nothing copies a file into a program to keep it; it points at it.

**Writing goes through one door**, so the record stays true and the room is counted.

A record of each file says where it came from — the owner, the AI (with model, prompt
and cost), a client through which program, a program, an agent — and its size, which
counts toward the owner's plan.

**Deleting is never final at once.** A file goes to the trash for 30 days and comes back
with a restore. Only the owner empties the trash.

**Room:** 100 MB on Free, 5 GB on Pro, 50 GB on Business, across all of the owner's
systems, trash included. One file can be the whole allowance on Free and up to 2 GB on a
paid plan. When the store is full, saving fails with the reason.

## From your agent

```
list_files(system, folder=, search=, trash=)    → items with size, origin, and a url that downloads
save_file(system, name, folder=, text= | from_url=)
delete_file(system, file)                        → to the trash
```

`save_file` takes either `text` — for anything textual: a price list, a CSV, a prompt, a
note — or `from_url`, which fetches a publicly reachable file and stores it. Folders are
made as needed; a taken name gets a number (`poster (2).png`).

A file your agent saves is immediately readable by every program of that system at
`/files/<folder>/<name>`. That is the simplest way to hand a running system a body of
data: write the file, then tell the program about it.

## Inside a program

```python
import os, httpx
SYS, H = "http://backend:8004/_system", {"Authorization": "Bearer " + os.environ["BNOME_TOKEN"]}

r = httpx.post(f"{SYS}/files", headers=H, content=data, timeout=120, params={
    "folder": "Clients/Ivan Petrov", "name": "bike.jpg",
    "origin": "client", "client": "ivan@example.com"})
r.json()    # {"ok": true, "id": "…", "path": "Clients/Ivan Petrov/bike.jpg", "url": …}

httpx.get(f"{SYS}/files", headers=H, params={"folder": "Clients"}).json()["items"]
httpx.delete(f"{SYS}/files/{file_id}", headers=H)       # to the trash
```

`origin` is `client` for what a client of the business sent (and `client` says who), or
`program` for what the program made itself. The program keeps the file's id on its own
row — an order's photo — and shows it to a browser by reading `/files/<path>` or by
handing out the `url`.
