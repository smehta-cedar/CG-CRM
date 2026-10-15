# CG-CRM — Backend

Django 5.2 + DRF API for the Cedar Grove CRM. Email-based auth, JWT, and a
role/permission system driven by a database-backed catalog.

## Getting started

```bash
cd backend
venv/Scripts/activate          # Windows;  source venv/bin/activate elsewhere
pip install -r requirements.txt
python manage.py migrate
python manage.py seed --email you@example.com
python manage.py runserver
```

`seed` prints a generated password once and flags the account to change it at
first sign-in. Pass `--password` to choose one yourself.

Settings are selected by `.env`:

```
settings_module=config.settings.local
```

## API docs

| | |
|---|---|
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| OpenAPI schema | http://localhost:8000/api/schema/ |

Or generate the schema as a file — useful for frontend codegen, or to import
into Postman (*Import → File → schema.yml*, which builds a collection):

```bash
python manage.py spectacular --fail-on-warn --file schema.yml
```

`--fail-on-warn` is worth keeping in CI. It catches views the schema generator
cannot describe, which is usually a sign something is mis-wired.

## Endpoints

All under `/api/v1/`. Everything except `auth/login/` requires
`Authorization: Bearer <access>`.

| Method | Path | Permission |
|---|---|---|
| POST | `auth/login/` | — |
| POST | `auth/change-password/` | any signed-in user |
| POST | `auth/token/refresh/` · `verify/` · `blacklist/` | — |
| GET | `permissions/` | any signed-in user |
| GET, POST | `roles/` | `role.detail` · `role.create` |
| GET, PATCH, DELETE | `roles/{id}/` | `role.detail` · `role.update` · `role.delete` |
| GET, POST | `users/` | `user.detail` · `user.create` |
| GET, PATCH | `users/{id}/` | `user.detail` · `user.update` |
| GET | `users/me/` | any signed-in user |
| POST | `users/{id}/block/` · `unblock/` | `user.block` · `user.unblock` |
| POST | `users/{id}/change-password/` | `user.change_password` |
| GET | `agencies/` | `agencies` view |
| POST | `agencies/create/` | `agencies` create |
| GET, PATCH, DELETE | `agencies/{id}/` | `agencies` view · update · delete |
| GET | `agencies/{id}/notes/` | `agencies` view |
| GET | `carriers/` | `carriers` view |
| POST | `carriers/create/` | `carriers` create |
| GET, PATCH, DELETE | `carriers/{id}/` | `carriers` view · update · delete |
| GET | `carriers/{id}/notes/` | `carriers` view |
| GET | `agents/` | `agents` view |
| POST | `agents/create/` | `agents` create |
| GET, PATCH, DELETE | `agents/{id}/` | `agents` view · update · delete |
| GET | `agents/{id}/notes/` | `agents` view |
| GET | `passwords/` | `passwords` view |
| POST | `passwords/create/` | `passwords` create |
| GET, PATCH, DELETE | `passwords/{id}/` | `passwords` view · update · delete |
| GET | `passwords/{id}/notes/` | `passwords` view |
| GET | `sites/` | `passwords` view |
| POST | `sites/create/` | `passwords` create |
| GET, PATCH, DELETE | `sites/{id}/` | `passwords` view · update · delete |
| GET | `site-passwords/` | `passwords` view |
| POST | `site-passwords/create/` | `passwords` create |
| GET, PATCH, DELETE | `site-passwords/{id}/` | `passwords` view · update · delete |
| GET | `site-passwords/{id}/notes/` | `passwords` view |
| GET | `contracts/` | `contracts` view |
| POST | `contracts/create/` | `contracts` create |
| GET, PATCH, DELETE | `contracts/{id}/` | `contracts` view · update · delete |
| GET | `contracts/{id}/notes/` · `contracts/notes/` | `contracts` view |
| GET | `users/{id}/notes/` · `users/notes/` | `users` view |
| GET | `roles/` | `users` view |
| GET | `roles/modules/` | superuser |
| POST | `roles/create/` | superuser |
| GET, PATCH, DELETE | `roles/{id}/` | `users` view · superuser · superuser |
| GET | `requests/` | `requests` view |
| POST | `requests/create/` | `requests` create |
| POST | `requests/merch/` | `requests` or `storefront.shop` create |
| GET, PATCH, DELETE | `requests/{id}/` | `requests` view · update · delete |
| GET | `storefront/catalog/` | public |
| GET | `storefront/products/` | `storefront.products` view |
| POST | `storefront/products/create/` | `storefront.products` create |
| GET, PATCH, DELETE | `storefront/products/{id}/` | `storefront.products` view · update · delete |
| GET | `storefront/products/{id}/notes/` | `storefront.products` view |
| GET | `policy-types/` | `carriers` or `agencies` view |
| POST | `policy-types/create/` | `carriers` or `agencies` create |
| GET, PATCH, DELETE | `policy-types/{id}/` | `carriers` or `agencies` view · update · delete |
| GET | `policy-types/{id}/notes/` | `carriers` or `agencies` view |
| GET | `carrier-policies/` | `carriers` view |
| POST | `carrier-policies/create/` | `carriers` create |
| GET, PATCH, DELETE | `carrier-policies/{id}/` | `carriers` view · update · delete |
| GET | `carrier-policies/{id}/notes/` | `carriers` view |
| GET | `certifications/` | `agents` view |
| POST | `certifications/create/` | `agents` create |
| GET, PATCH, DELETE | `certifications/{id}/` | `agents` view · update · delete |
| GET | `certifications/{id}/notes/` | `agents` view |

Permission codes follow the sidebar links (`MODULES` in
`apps/accounts/models/roles.py`): `dashboard` (Overview), `agents.list`,
`agents.profile`, `carriers.list`, `carriers.profile`, `rulebook`,
`passwords`, `contracts.by_state`, `contracts.by_carriers`, `requests`
(Calendar), `storefront.products`, `storefront.shop`, `users`, `agencies`
(Agency). A section code in the table
(`agents`, `carriers`, `contracts`) is allowed when any of its sub-links is.

Agents sign in with the built-in Agent role's permissions, the same codes as
staff. The own-records layer (`own_only` / `ensure_own` in
`apps/base/api/permissions.py`) narrows them: requests (Calendar) are read and
written only for the agent's own record, contracts are read in full but
added, changed or deleted only for their own, and a Shop order is filed under
them.

`GET /agencies/` takes `?search=` (name, alias, NPN, email, phone) and
`?is_active=`, plus `?page=` / `?page_size=`.

`GET /carriers/` takes `?search=` (name, alias, line of business),
`?is_active=` (true only for status `active`, i.e. in force) and `?state=`
(two-letter code), plus `?page=` / `?page_size=`; rows come back by name. A
carrier's `status` is `active`, `applied`, `pending`, `expired` or `inactive`
and `links` a list of named URLs (`[{"name", "url"}]`, each name once,
ignoring case; an update that sends it replaces the list). Its states are `licenses`, rows like an agent's
licences (`state`, `license_number`, `status`, `start_date`, `end_date` as
the expiration, `life`, `health`); a create or update that sends `licenses`
replaces the set, and `available_states` (read-only, state codes in code
order) always equals the rows' states. Its `lines_of_business` at least one of
`Medicare Supplement`, `Ancillary`, `MAPD`, `Life`, `Annuities` on every
save (carriers that only had the retired `General` were left with none;
`Supp/Ancillary` was renamed `Ancillary`). The API records a
change note on every create and on every update that changed something;
`carriers/{id}/notes/` lists them newest first. Load the carriers from the
frontend's seed file with:

```bash
python manage.py seed_carriers            # frontend/data/carriers.json
python manage.py seed_carriers --file path/to/carriers.json
```

`GET /agents/` takes `?search=` (name, alias, NPN, email, phone), `?is_active=`,
`?status=` and `?state=` (licensed there), plus paging; rows come back by name.
An agent's `status` is active, onboarding, sdr or inactive; `is_active` follows
it (false only for inactive), so onboarding and SDR agents can sign in. An agent
carries `address` (all four parts or `null`) and `licenses`, its state licence
rows (`state`, `license_number`, `status` of active / review / pending / jit,
`start_date`, `end_date`). On create and update, `licenses` is the full set
of licensed states with their numbers: a listed state keeps its row with the
number as given, an unlisted one loses its row, a new one gets an active row
starting today and running two years. NPN is unique among live agents.

`GET /policy-types/` (the catalog of policy kinds, `apps.policies`: its own
entity, not a carrier's line of business, and unrelated to certifications)
takes `?search=` (name) and `?is_active=`, plus paging; rows come back by
name. A policy type is a `name` (unique among live rows, ignoring case) and
a status. Change notes as for carriers; `policy-types/{id}/notes/` lists
them newest first.

`GET /carrier-policies/` (one named policy a carrier offers, also in
`apps.policies`; guarded by the `carriers` permission, since a policy lives
on its carrier) takes `?search=` (name), `?carrier=`, `?policy_type=` and
`?is_active=`, plus paging; rows come back by name and carry `carrier` and
`policy_type` summaries. A policy has a `carrier`, a `policy_type` from the
catalog, a `name` (unique among that carrier's live policies, ignoring case;
two carriers may share a name) and `available_states`, the codes where it
can be sold. Every state must be on the carrier's own `available_states`;
one that is not is a 400 naming the state. Empty means nowhere, never every
state. The carrier cannot change on PATCH. Change notes as for carriers,
listing name, policy type (by name), carrier (by name), available states
and status; `carrier-policies/{id}/notes/` lists them newest first.

`GET /certifications/` (an agent's yearly certification with a carrier for
one of its lines of business, also in `apps.policies`, guarded by
the `agents` permission; policy types play no part) takes
`?agent=`, `?carrier=` and `?line_of_business=`, plus paging; rows come back
by agent name, then due date, carrier name and line of business, and carry
`agent` and `carrier` summaries. A certification has an `agent` (the only
required field), an optional `carrier`, a `line_of_business` (one of the
carrier lines, or blank; the sub type), a `due_date` (defaults to the next
deadline, set by `CERTIFICATION_DUE_MONTH` / `CERTIFICATION_DUE_DAY` in
settings, Sept 15 for now), optional `start_date` / `end_date`, `is_verified`,
an optional PDF and a status. It is an add-on: nothing else is checked, and
the same row may be added twice. Change notes as for carriers, listing agent
and carrier (by name), line of business, due date, start date, end date,
verified, status and file; `certifications/{id}/notes/` lists them newest
first.

Creating a contract (`POST /contracts/create/`) also gives the agent a
certification per line of business of that carrier, due on the next
deadline; lines already covered for it are skipped. `python manage.py
add_contract_certifications [--due YYYY-MM-DD]` does the same for every
contract (and dates any undated row); it is safe to rerun, and running it
after a deadline starts the next year's rows.

`GET /passwords/` (carrier portal logins, one per agent + carrier) takes
`?search=` (username, agent name, carrier name), `?agent_id=`, `?carrier_id=`
and `?status=` (active / pending / inactive), plus paging; rows come back by
agent name then carrier name and carry `agent` and `carrier` summaries. The
portal password is returned as stored; its change notes only ever say it was
set or changed (`"redacted": true`).

Logins that aren't at a carrier are **site passwords**, in the same app and
under the same `passwords` permission. `GET /sites/` lists sites (a `name`,
unique among live sites whatever its case, an optional `link` URL, and
`password_count`), by name; `DELETE /sites/{id}/` is refused (400, under `site`) while live
site passwords use the site. `GET /site-passwords/` takes `?search=`
(username, agent or agency name, site name), `?agent_id=`, `?agency_id=`,
`?site_id=` and `?status=`; rows carry an `agent` or `agency` summary and a
`site` summary (with its link), by agent name then site name. One live site password per
agent + site and per agency + site (errors under `site_id`); there is no
contract-number rule. Migration `passwords.0008` undid `0007` (which had
briefly turned every password's carrier into free-text `site`): a site
naming a carrier got that carrier back, any other became a site password.

For both kinds, `username` and `portal_password` may be blank only while
`status` is `pending`; otherwise a blank one is a 400 under that field. A
PATCH is checked against the values the password ends up with.

Adding a carrier gives a **pending password** automatically: creating an
appointment (`POST /contracts/create/`) gives that agent a pending carrier
password there, and creating an agency contract gives the agency one, with a
blank username and password and an "added" note. A PATCH that moves a
contract to a new carrier (or agent) does the same; other edits don't, so a
pending password deleted on purpose stays deleted. Nothing is added when a
live password already exists. `python manage.py add_pending_passwords` does
the same for every existing live contract; it is safe to rerun.

An agency contract has a `status`, the same set as an agency licence:
`active` (the default), `pending`, `applied`, `expired` or `cancelled`. An
active contract needs a `contract_number` (400 under it); any other status
may leave it blank. A carrier is open to agents (appointments, portal
passwords) only while its contract is active and has a number.

An agency contract's create and PATCH also take `agents`, a list of agent
IDs to appoint with its carrier in the same save: each gets a `pending`
appointment with no writing number or states, its "added" note, this year's
certifications and a pending password, as if added on Contracts. Agents
already appointed there are skipped. It needs the `contracts` create
permission (403 otherwise) and an active contract with a number (400 under
`agents`).

`GET /contracts/` (appointments: one agent contracted with one carrier)
takes `?search=` (agent name, carrier name, writing number), `?agent_id=`,
`?carrier_id=` and `?state=`, plus paging; rows come back by agent name then
carrier name. `appointed_states` must be states the carrier is available in
*and* the agent is licensed in; the 400 names the side that blocks a state.
The writing number is unique within a carrier when set (ignoring case).

`users/` gained change notes: every create, update that changed something,
block / unblock and password set writes one (the password only as
`"redacted": true`), read at `users/{id}/notes/` or all at once at
`users/notes/`.

`GET /roles/` lists every live role with its `permissions` (one row per
module with `can_view` / `can_create` / `can_update` / `can_delete`) and a
`user_count`; it takes `?search=` (name, description) and `?is_active=`, and
is not paginated. Only a superuser may create, update or delete a role;
`roles/modules/` lists the modules (the `MODULES` catalog in
`apps/accounts/models/roles.py`) a role can be granted. On create and update
`permissions` is the full set: a module left out gets no access, and create,
update or delete on a module also needs view. Deleting is refused while any
live user still holds the role. The frontend's Roles page is shown to
superusers only.

Seed everything from the frontend's JSON, in this order (passwords and
contracts refer to agents and carriers):

```bash
python manage.py seed_carriers
python manage.py seed_agents              # agents.json + agent-state-licenses.json
python manage.py seed_passwords           # passwords.json, matched by NPN and carrier name
python manage.py seed_site_passwords      # site-passwords.json; creates the sites it names
python manage.py seed_contracts           # carrier-contracts.json, same matching
python manage.py seed_users               # users.json + default permissions on empty built-in roles; local dev only
python manage.py seed_agency              # agency.json + agency-state-licenses.json
python manage.py seed_storefront          # the Cedar Grove tee
python manage.py seed_requests            # requests.json + merch-requests.json, and the shop account
```

`storefront/catalog/` is the one public endpoint: every active product
(name, description, `category` and `product_type` for the shop's nav,
`image_url`, price, `colors` as {id, label, hex}, `sizes`, `max_quantity`)
for the shop page, no sign-in. Categories are womens / mens / maternity /
accessories / holidays and types polos / quarter-zips / shirts / pants /
belts / hats / backpacks (`PRODUCT_CATEGORIES`, `PRODUCT_TYPES` in
`apps/storefront/models`); both may be blank. `storefront/products/`
takes `?category=` and `?product_type=` too. The `storefront/products/`
endpoints manage them (at least one colour and one size; change notes as
elsewhere). A merch order (`requests/merch/`) names its `product_id` and
is checked against that product's colours, sizes and `max_quantity`; it
stores the colour's label. Run `seed_storefront` before `seed_requests` so
the seeded orders link to the tee.

`GET /requests/` (HR: an agent's licensing, contract or day-off request, or
a tee order from the public shop) takes `?type=`, `?status=` and
`?agent_id=`, plus paging; rows come back oldest first. `requests/create/`
files an agent's request (licensing and contract need `state` and
`carrier_id`, `day_off` its two dates); `requests/merch/` files a shop
order. The shop has no sign-in, so the Next server posts orders as the
`shop@cedargrove.local` account that `seed_requests` creates with a `Shop`
role (requests: view and create only); its password is printed once and
goes in `frontend/.env.local` as `SHOP_API_PASSWORD`. A `PATCH` sets the
status (pending / applied / approved / denied) or the note.

An agency carries `licenses` (state licence rows) exactly like an agent and
takes `licenses` on create and update the same way, except that each row
also takes a `status` (active / pending / review / applied / expired /
cancelled; jit is accepted too) and, like an agent's, a `start_date` and
`end_date`: a new row is active and runs today to two years on unless they
are given, and a kept row keeps whatever is left out or null. The change
note lists `license_statuses` and `license_dates` alongside the states and
numbers. `agencies/{id}/notes/` lists its change notes.

Written notes are separate from the change log: `GET agencies/{id}/comments/`
lists them newest first (`body`, `created_by`, `created_at`), `POST` with
`{"body"}` adds one, and `DELETE agencies/comments/{id}/` removes one (soft
delete). Adding and deleting need the `agencies` update permission.

An agency PATCH also takes `agent_licenses`, a list of `{"state", "agents"}`:
each listed agent gets a `pending` licence in that state with no number or
dates, and an "edited" note on the agent. Agents already licensed there are
skipped. It needs the `agents` update permission (403 otherwise).

Three roles are built in: Admin, Operations and Agent. A migration creates
them (an old Staff role becomes Operations, users and all), and the API
refuses to delete, rename or switch them off; their description and
permissions are edited on the Roles page like any other role. Every agent
sign-in takes its permissions from Agent.

`seed_users` sets passwords exactly as the file holds them, skipping the
strength validators. A built-in role with no permissions yet gets defaults:
Admin every action on every module, Operations view on every module, Agent
view and create on Calendar. A role that already has
permissions is left as set. `"staff"` in users.json means Operations. It
never touches a superuser.

`GET /permissions/` returns the catalog grouped `Module → Resource → Actions`
for the checkbox tree. `GET /users/me/` returns the signed-in account with its
role and effective permission codenames — the frontend renders its menus from
that list.

## Access control

All policy lives in one function, `apps/roles/permissions.py::check_access`.
Two wrappers call it and nothing else, so the rules cannot drift apart:

```python
# viewsets
class RoleViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasRolePermission]
    required_permissions = {'list': 'role.detail', 'create': 'role.create'}

# plain view methods
@require_permission('user.create')
def post(self, request): ...
```

Checks run in this order:

1. **Authenticated** → else 401.
2. **Not blocked** → else 403 `account_blocked`.
3. **No pending forced password change** → else 403 `password_change_required`.
4. **Superuser** → pass, without consulting a role.
5. **Role holds the codename** → else 403 `permission_denied`.

Steps 2 and 3 sit *above* the superuser bypass on purpose: a blocked or
just-reset admin is held to the same rule as anyone else.

Refusals carry a machine-readable `code` in the response body, because the
frontend has to tell "you lack this permission" (show an error) from "you must
change your password" (redirect).

**Fails closed.** An action missing from a view's `required_permissions` is
denied. Forgetting a codename should cost a 403 in a test, not leave an
endpoint open. Use `ANY_AUTHENTICATED` to open one deliberately.

**The allow-list.** `POST auth/change-password/` and `GET users/me/` stay
reachable while a forced change is pending — gate the endpoint that clears the
flag on the flag being clear and the user can never get out.

## The permission catalog

`apps/roles/catalog.py` is the source of truth. Ten permissions across two
modules: `user.create|update|detail|block|unblock|change_password` and
`role.create|update|detail|delete`.

Adding one takes **two** steps:

1. Add it to `catalog.py`.
2. Add a data migration alongside it (see
   `roles/migrations/0002_seed_permissions.py`).

The migration carries a *frozen* copy rather than importing `catalog.py` — a
migration has to keep describing the world as it was, or replaying history
produces whatever today's catalog happens to say. `test_catalog_matches_the_database`
fails if you do step 1 without step 2.

| Command | Use |
|---|---|
| `manage.py seed` | Fresh environment: catalog + Super Admin role + first admin |
| `manage.py seed_permissions` | Routine deploys: catalog only |
| `manage.py seed_permissions --prune` | Drop permissions no longer in the catalog |

Both are idempotent. `seed` never resets an existing account's password, so
re-running it is not a way to take over an account.

## Auth notes

**Login** returns `access`, `refresh`, `must_change_password`, and the full
`user` object (saving an immediate round trip to `users/me/`). It distinguishes
three failures by `code`: `invalid_credentials`, `account_blocked`,
`account_inactive`.

The specific reason is only disclosed *after* the password is proven correct —
a blocked account with the wrong password returns exactly what an unknown
address returns. Otherwise the endpoint is an account-enumeration oracle.

**Token invalidation** uses `User.token_version`, stamped into every JWT and
checked on each request. The blacklist app only covers *refresh* tokens; access
tokens are stateless and would stay valid for up to `ACCESS_TOKEN_LIFETIME`
after a block. Bumping the counter closes that window immediately and costs
nothing — authentication already loads the user row. Blocking does both.

`token_version` is bumped on block, on an admin password reset, and on a
self-serve password change (which ends your *other* sessions; the endpoint
hands back a fresh pair so you keep the one you are in).

There is **no `POST auth/token/`**. SimpleJWT's stock view cannot tell the
failure modes apart, does not report `must_change_password`, and mints tokens
with no version stamp — a permanent hole in blocking.

## Model notes

- **`User`** — `AbstractBaseUser` + `PermissionsMixin`, email as
  `USERNAME_FIELD`, no username. Email is lowercased whole (not just the
  domain) so the unique constraint cannot be defeated by `Ada@` vs `ada@`.
- **`login_type`** — an **auth provider** field: `local` or `sso`. Not a user
  category; `Role` covers that. An SSO account holds no local password and is
  not flagged `must_change_password`, which would strand it.
- **`User.role`** — `on_delete=PROTECT`. A role that is still assigned must not
  be deletable; `RoleDeleteSerializer` turns the resulting `ProtectedError`
  into a readable 400, but the database is what guarantees it. A serializer
  alone would be bypassed by a shell session or a `queryset.delete()`.
- **No user delete route.** Accounts are deactivated (`is_active`) or blocked
  (`is_blocked`), so records referencing them keep making sense.
- **`Agency`** — `name` is unique case-insensitively among live rows; `npn`
  (National Producer Number, 1-10 digits) is unique among live rows when
  set, and blank is allowed. `aliases` is a JSON list of strings, trimmed and
  de-duplicated on write. `is_active` from `BaseModel` is whether the agency
  is operating.
- **`State`** — the US states (plus DC) as a lookup table: `name`, two-letter
  `code` (stored uppercase), and `search_key`, a comma-separated list of
  lowercase terms a search may match (`"california,ca"`). Seeded by
  `agency/migrations/0003_seed_states.py`, which carries a frozen copy of
  `US_STATES` for the same reason the permission catalog does.

## Tests

```bash
python manage.py test apps          # 180 tests
python manage.py test apps.roles
```

The three parts most worth reading, because they encode decisions rather than
mechanics:

| | Where |
|---|---|
| Role delete guard | `apps/roles/tests.py::RoleDeleteGuardTests` |
| Blocked-user login | `apps/users/test_auth.py::LoginTests`, `BlockUnblockTests` |
| Forced password change | `apps/roles/test_access.py::PasswordChangeGateEndToEndTests` |

## Layout

```
backend/
  config/settings/{base,local,dev,prod}.py
  apps/
    users/    User, auth, JWT, the user API
    roles/    Permission, Role, the catalog, check_access
    agency/   Agency (name, aliases, NPN, contact, is_active) and its API
```

`manage.py startapp <name>` creates apps under `apps/` and rewrites the
generated `AppConfig` to its dotted path. Add it to `LOCAL_APPS`.

## Known gaps

- **No pagination.** List endpoints return plain JSON lists. Fine for roles;
  `users/` will want `DEFAULT_PAGINATION_CLASS` before the table grows.
- **`dev.py` and `prod.py` are empty.** Only `local.py` is filled in, and its
  `SECRET_KEY` is the checked-in development one.
- **No rate limiting on login.** Worth adding before this is public.
- **SSO is a field, not an integration.** Nothing implements `login_type=sso`
  yet.
