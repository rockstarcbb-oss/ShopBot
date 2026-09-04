# AiogramShopBot Docs

Full documentation for deployment, configuration, user flows, admin flows, referral logic, SQLAdmin, multibot mode, and media demos.

## Table of Contents

- [Deployment and configuration](#deployment-and-configuration)
- [User manual](#user-manual)
- [Admin manual](#admin-manual)
- [Cryptocurrency forwarding](#cryptocurrency-forwarding)
- [Referral system](#referral-system)
- [SQLAdmin web admin panel](#sqladmin-web-admin-panel)
- [Multibot experimental](#multibot-experimental)
- [Demo gallery](#demo-gallery)
- [Todo list](#todo-list)

## Deployment and Configuration

### Required environment variables

| Environment Variable Name    | Description | Recommended Value |
|------------------------------|-------------|-------------------|
| `WEBHOOK_PATH` | The path to the webhook where Telegram servers send requests for bot updates. Change it if you deploy several bots on one server. | `/` |
| `WEBAPP_HOST` | Hostname for the Telegram bot service. | `0.0.0.0` for Docker Compose, `localhost` for local deployment |
| `WEBAPP_PORT` | Port for the Telegram bot service. | `5000` |
| `TOKEN` | Telegram bot token from `@BotFather`. | No recommended value |
| `ADMIN_ID_LIST` | Comma-separated list of Telegram IDs that can access the admin menu. | No recommended value |
| `SUPPORT_LINK` | Telegram support profile URL used by the Help button. | `https://t.me/${YOUR_USERNAME_TG}` |
| `POSTGRES_USER` | PostgreSQL username. | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password. | Any strong value |
| `DB_PORT` | PostgreSQL port. | `5432` |
| `DB_HOST` | PostgreSQL host. | `postgres` |
| `NGROK_TOKEN` | Ngrok token for development tunnel mode. | No recommended value |
| `PAGE_ENTRIES` | Pagination size. | `8` |
| `MULTIBOT` | Enables experimental multibot mode. Accepts `"true"` or `"false"`. | `"false"` |
| `CURRENCY` | Fiat currency used in the bot. | `"USD"`, `"EUR"`, `"JPY"`, `"CAD"`, or `"GBP"` |
| `RUNTIME_ENVIRONMENT` | `"dev"` uses ngrok, `"prod"` uses reverse proxy flow. | `"prod"` or `"dev"` |
| `WEBHOOK_SECRET_TOKEN` | Protects Telegram webhook requests from spoofing. | Any strong value |
| `KRYPTO_EXPRESS_API_KEY` | API key from KryptoExpress. | No recommended value |
| `KRYPTO_EXPRESS_API_URL` | KryptoExpress API URL. | `https://KryptoExpress.pro/api` |
| `KRYPTO_EXPRESS_API_SECRET` | Protects KryptoExpress callbacks from spoofing. | Any strong value |
| `REDIS_PASSWORD` | Required for throttling. | Any strong value |
| `REDIS_HOST` | Redis host. | `redis` for Docker Compose |
| `CRYPTO_FORWARDING_MODE` | Enables automatic forwarding of deposits to your own addresses. | `"true"` or `"false"` |
| `BTC_FORWARDING_ADDRESS` | Required when forwarding mode is enabled. | Bech32 BTC address |
| `LTC_FORWARDING_ADDRESS` | Required when forwarding mode is enabled. | Bech32 LTC address |
| `ETH_FORWARDING_ADDRESS` | Required when forwarding mode is enabled. | Ethereum address |
| `SOL_FORWARDING_ADDRESS` | Required when forwarding mode is enabled. | Solana address |
| `BNB_FORWARDING_ADDRESS` | Required when forwarding mode is enabled. | BNB address |
| `MIN_REFERRER_TOTAL_DEPOSIT` | Deposit threshold to unlock referrals. | `"500"` |
| `REFERRAL_BONUS_PERCENT` | Referral bonus percent for invited users. | `"5"` |
| `REFERRAL_BONUS_DEPOSIT_LIMIT` | Number of referred-user deposits eligible for bonus. | `"3"` |
| `REFERRER_BONUS_PERCENT` | Bonus percent for the inviter. | `"3"` |
| `REFERRER_BONUS_DEPOSIT_LIMIT` | Number of deposits per referral that reward the inviter. | `"5"` |
| `REFERRAL_BONUS_CAP_PERCENT` | Cap for referred-user bonus. | `"7"` |
| `REFERRER_BONUS_CAP_PERCENT` | Cap for inviter bonus. | `"7"` |
| `TOTAL_BONUS_CAP_PERCENT` | Global combined bonus cap. | `"12"` |
| `SQLADMIN_RAW_PASSWORD` | Password for SQLAdmin login. | Strong random string |
| `JWT_EXPIRE_MINUTES` | JWT expiration time for SQLAdmin auth. | `"30"` |
| `JWT_ALGORITHM` | JWT algorithm. | `"HS256"` |
| `JWT_SECRET_KEY` | Secret for JWT generation. | Strong random string |

### Quick start

Run on a VPS:

```bash
sudo sh -c "$(curl -fsSL https://raw.githubusercontent.com/ilyarolf/AiogramShopBot/refs/heads/master/scripts/deploy.sh)"
```

The interactive script will prompt you for `.env` values.

### Development and production mode

For local development on a computer that is not internet-facing, set `RUNTIME_ENVIRONMENT="dev"`. The bot will use an ngrok tunnel.

> **Note**  
> You need a valid ngrok account and token. Redis is still required.

For production, you can use your own hostname behind Caddy or services like [sslip.io](https://sslip.io/). Caddy can automatically provision TLS and act as a reverse proxy. If you already have a reverse proxy, remove the Caddy service and configure routing yourself.

### Local development example

> **Note**  
> Local deployment still requires PostgreSQL, Redis, and a reverse proxy or tunnel setup.

```bash
git clone https://github.com/ilyarolf/AiogramShopBot.git
pip install -r requirements.txt
python run.py
```

Example `.env`:

```env
WEBHOOK_PATH="/"
WEBAPP_HOST="localhost"
WEBAPP_PORT=5000
TOKEN="1234567890:QWER.....TYI"
ADMIN_ID_LIST=123456,654321
SUPPORT_LINK="https://t.me/your_username_123"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="qwertyu"
DB_PORT="5432"
DB_HOST="localhost"
POSTGRES_DB="aiogram-shop-bot"
NGROK_TOKEN="NGROK_TOKEN_HERE"
PAGE_ENTRIES="8"
MULTIBOT="false"
CURRENCY="USD"
RUNTIME_ENVIRONMENT="PROD"
WEBHOOK_SECRET_TOKEN="1234567890"
KRYPTO_EXPRESS_API_KEY="API_KEY_HERE"
KRYPTO_EXPRESS_API_URL="https://kryptoexpress.pro/api"
KRYPTO_EXPRESS_API_SECRET="1234567890"
REDIS_PASSWORD="1234567890"
REDIS_HOST="localhost"
CRYPTO_FORWARDING_MODE="false"
BTC_FORWARDING_ADDRESS=""
LTC_FORWARDING_ADDRESS=""
ETH_FORWARDING_ADDRESS=""
SOL_FORWARDING_ADDRESS=""
BNB_FORWARDING_ADDRESS=""
MIN_REFERRER_TOTAL_DEPOSIT="500"
REFERRAL_BONUS_PERCENT="5"
REFERRAL_BONUS_DEPOSIT_LIMIT="3"
REFERRER_BONUS_PERCENT="3"
REFERRER_BONUS_DEPOSIT_LIMIT="5"
REFERRAL_BONUS_CAP_PERCENT="7"
REFERRER_BONUS_CAP_PERCENT="7"
TOTAL_BONUS_CAP_PERCENT="12"
SQLADMIN_RAW_PASSWORD="admin"
JWT_EXPIRE_MINUTES="30"
JWT_ALGORITHM="HS256"
JWT_SECRET_KEY="1234567890"
```

## User Manual

### Registration

User registration happens automatically on the first `/start` command.

### Top up balance

- Open `👤 My profile`
- Open `➕ Top Up Balance`
- Select a cryptocurrency
- Copy the payment address
- Send crypto and wait for confirmation

### Purchase of goods

Open `All categories`, pick a city (`💾 Panevezys` or `🏷️ Kaunas`), select a category, select a subcategory, choose the quantity, add it to the cart and confirm the purchase.

Every purchase is delivered immediately after the balance is charged, no matter which city the item comes from: the bot sends the item data and, when the seller attached one, the delivery photo (QR code, game card, pickup code, parcel photo, ...) with the data in the caption below it. There is no shipping address and no shipping option step - a Kaunas item is bought exactly like a Panevezys one. You can reopen the same data and photo later from `My Profile -> Purchase History`.

### Purchase history

Open `My Profile -> Purchase History` to see previous purchases and open details for each one.

## Admin Manual

### Adding a new admin

Add the Telegram ID to `ADMIN_ID_LIST`, separated by commas, and restart the bot.

Example:

```env
ADMIN_ID_LIST=123456,654321
```

### Announcements

#### Send to Everyone

- Open `🔑 Admin Menu`
- Open `📢 Announcements`
- Select `📢 Send to Everyone`
- Type or forward a message
- Confirm or decline the sending

![Send to Everyone](https://i.imgur.com/JYN6qx0.gif)

#### Restocking Message

Generated from items where `is_new = true`.

![Restocking Message](https://i.imgur.com/lu3khwR.gif)

#### Current Stock

Generated from items where `is_sold = false`.

![Current Stock](https://i.imgur.com/T9wMPRG.gif)

### Inventory Management

Items from both cities are added the same way: every item carries the data the buyer
receives (`private_data`) and, optionally, a delivery photo (`delivery_image`).

> **Note**  
> Kaunas stock that was added before this change has no data and no photo attached, so
> buying it would deliver an empty message. Re-add that stock with its data (or fill in
> `private_data` / `delivery_image` in the SQLAdmin panel) before selling it.

#### Add Items via JSON

Send a `.json` file after opening `🔑 Admin Menu -> 📦 Inventory Management -> ➕ Add Items -> JSON`.

> **Note**  
> `private_data` is what the user receives after purchase.

Example:

```json
[
  {
    "item_type": "Physical",
    "category": "Category#1",
    "subcategory": "Subcategory#1",
    "price": 50,
    "description": "Mocked description",
    "private_data": "Mocked private data",
    "delivery_image": "https://example.com/image.png"
  },
  {
    "item_type": "Digital",
    "category": "Category#2",
    "subcategory": "Subcategory#2",
    "price": 100,
    "description": "Mocked description",
    "private_data": "Mocked private data",
    "delivery_image": "https://example.com/qr-code.png"
  }
]
```

![Add Items JSON](https://i.imgur.com/zjS4v8k.gif)

#### Add Items via TXT

Open `🔑 Admin Menu -> 📦 Inventory Management -> ➕ Add Items -> TXT` and send a `.txt` file.

Example:

```txt
PHYSICAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#1;https://example.com/image1.png
PHYSICAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#2;https://example.com/image2.png
PHYSICAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#3
PHYSICAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#4
DIGITAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#5;https://example.com/qr-code.png
DIGITAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#6;https://example.com/qr-code.png
DIGITAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#7
DIGITAL;CATEGORY#1;SUBCATEGORY#1;DESCRIPTION#1;50.0;PRIVATE_DATA#8
```

Both cities use the same columns: `ITEM_TYPE;CATEGORY;SUBCATEGORY;DESCRIPTION;PRICE;PRIVATE_DATA[;DELIVERY_IMAGE]`.
`null` (or `-`) in the data column means the item has no data attached, and the delivery
image column is optional. `ITEM_TYPE` accepts `DIGITAL` / `PHYSICAL` or the city name
(`Panevėžys` / `Kaunas`), the same as in the JSON `item_type` field.

![Add Items TXT](https://i.imgur.com/jct3qGc.gif)

#### Add Items via MENU

Open `🔑 Admin Menu -> 📦 Inventory Management -> ➕ Add Items -> MENU` and follow the prompts:
item type (city), category, subcategory, description, data, delivery image(s) and price.

The item type step accepts `DIGITAL` / `PHYSICAL` as well as the city names shown in the
bot (`Panevėžys`, `Kaunas`, in any of the bot languages); anything else is re-asked.

> **Note**  
> Every line of the data you send becomes a separate item
> (1 line = 1 item, 10 lines = 10 items) - for Panevezys and Kaunas items alike.

After the data step the bot asks for a delivery image **for each line**, one by one
(`📷 Delivery photo 1 of 3`, `2 of 3`, ...). For every line you can:

- send a photo (photos sent as an album are assigned in order),
- send an image URL (`https://...`),
- send `skip` so that this line has no image.

Each buyer receives the photo that belongs to the item they purchased: if the items
have different photos, the buyer gets a separate photo for each one.

#### Delete category or subcategory

> **Note**  
> Deleting a category or subcategory removes all unsold products bound to it from `All categories`.

![Delete Category or Subcategory](https://i.imgur.com/foFKU0y.gif)

### User Management

#### Credit Management: Add balance

Find a user by Telegram ID or username and increase their balance.

![Add Balance](https://i.imgur.com/6HXd460.gif)

#### Credit Management: Reduce balance

Find a user by Telegram ID or username and reduce their balance.

![Reduce Balance](https://i.imgur.com/4JPbWZd.gif)

#### Make Refund

Select a purchase from the refund menu and confirm or cancel the refund.

![Make Refund](https://i.imgur.com/hZ7UvJJ.gif)

### Analytics and Reports

#### Statistics

Open `🔑 Admin Menu -> 📊 Analytics & Reports`, select an entity, then choose the time range.

![Statistics](https://i.imgur.com/lmuo0QY.gif)

### Admin notifications

> **Note**  
> All Telegram IDs from `ADMIN_ID_LIST` receive admin notifications.

#### New deposit notification

![New Deposit Notification](https://i.imgur.com/FSXzEoW.gif)

#### New buy notification

![New Buy Notification](https://i.imgur.com/MeRkCYD.gif)

### Media management

Open `🔑 Admin Menu -> 📷 Media management` to change category, subcategory, or button media.

> **Note**  
> Media can be GIFs, images, or videos.

![Media Management](https://i.imgur.com/VIQdxvL.gif)

### Coupons management

#### Create new coupon

Select the coupon type, usage limit, value, coupon name, then confirm or cancel.

![Create Coupon](https://i.imgur.com/1tfiFBw.gif)

#### View all coupons

Select an existing coupon and choose whether to enable or disable it.

![View Coupons](https://i.imgur.com/dMZoOA3.gif)

### Shipping management

> **Note**  
> Shipping is no longer part of the checkout: every city is delivered instantly, so new
> orders never ask for a shipping address or a shipping option. These screens are kept
> for orders that were placed before that change (their address, shipping option and
> track number are still shown in `Buys management` and in the buyer's purchase history).

#### Create new shipping option

Open `🔑 Admin Menu -> 📦 Shipping management -> 🚚 Create new shipping option`.

![Create Shipping Option](https://i.imgur.com/IqrdGL5.gif)

#### View all shipping options

Open `🔑 Admin Menu -> 📦 Shipping management -> 📋 View all shipping options`.

![View Shipping Options](https://i.imgur.com/E2MHoaK.gif)

### Buys management

Used mainly to view user purchases and update tracking numbers for legacy shipped orders.

![Buys Management](https://i.imgur.com/4aPUnHx.gif)

### Reviews management

Used to view and moderate customer reviews.

![Reviews Management](https://i.imgur.com/umBysXX.gif)

## Cryptocurrency Forwarding

You can enable cryptocurrency forwarding so deposits received via KryptoExpress are redirected to your own addresses.

To enable it:
- set `CRYPTO_FORWARDING_MODE=true`
- set the required `{CRYPTO}_FORWARDING_ADDRESS` values in `.env`

> **Note**  
> BTC and LTC forwarding addresses must use Bech32 format.

## Referral System

The referral system is designed to stimulate organic growth while keeping the bonus economy controlled and predictable. Bonuses are credited as internal balance and cannot be withdrawn.

### Access to the referral system

A user becomes eligible to use referrals only after reaching `MIN_REFERRER_TOTAL_DEPOSIT`.

### How referrals work

Each eligible user gets a unique referral link. When a new user joins via that link and later makes a deposit, the referral relationship becomes permanent.

### Referral bonuses for the referred user

- `REFERRAL_BONUS_PERCENT`
- `REFERRAL_BONUS_DEPOSIT_LIMIT`
- `REFERRAL_BONUS_CAP_PERCENT`

### Referrer bonuses for the inviting user

- `REFERRER_BONUS_PERCENT`
- `REFERRER_BONUS_DEPOSIT_LIMIT`
- `REFERRER_BONUS_CAP_PERCENT`

### Global bonus cap

`TOTAL_BONUS_CAP_PERCENT` limits the combined referral and referrer bonuses generated from a single referred user.

### Anti-abuse guarantees

- Access is locked behind a minimum deposit requirement
- Bonuses apply only to a limited number of deposits
- Individual and global caps are enforced
- Self-referrals are forbidden

## SQLAdmin Web Admin Panel

You can work with database objects using the SQLAdmin admin panel.

- URL: `{YOUR_IP_ADDRESS}.sslip.io/admin`
- Login: `admin`
- Password: `${SQLADMIN_RAW_PASSWORD}`

![SQLAdmin Panel](https://i.imgur.com/s1EpxNR.png)

## Multibot Experimental

### Starting the multibot

- Set `MULTIBOT="true"` in Docker Compose
- Start the stack with `docker-compose up`
- This launches one main manager bot
- Child bots are added only through the main bot
- Only Telegram IDs from `ADMIN_ID_LIST` can connect child bots
- To add a managed bot, send `/add {token}` to the main bot
- Connected child bot tokens are stored in Redis under `multibot:tokens`
- On startup, the app restores child bot webhooks from Redis automatically
- In multibot mode, direct user notifications and announcement delivery try all known bot tokens with a short delay between attempts

![Multibot](https://i.imgur.com/YAGjN3G.png)

## Demo Gallery

User-facing demos are shown in the main [README](readme.md). Additional admin demos in this file:

- Send to Everyone
- Restocking Message
- Current Stock
- Add Items JSON
- Add Items TXT
- Delete Category/Subcategory
- Credit Management
- Refunds
- Statistics
- Admin notifications
- Media management
- Coupons
- Shipping management
- Buys management
- Reviews management

## Todo List

- [x] Make migration from direct raw database queries to SQLAlchemy ORM.
- [x] Add option to encrypt database via SQLCipher when using SQLAlchemy.
- [x] Add option to generate new crypto addresses using new mnemonic phrases so that `1 user = 1 mnemonic phrase`.
- [x] Items pagination.
- [x] Database backup from Telegram admin actions.
- [x] Sales and users statistics in Telegram admin.
- [x] Deposit statistics in Telegram admin.
- [x] Product sorting by name, quantity, and price.
- [x] Product search and filtering.
- [x] Cryptocurrency forwarding mode.
- [x] Media for categories, subcategories, and buttons.
- [x] Improved shopping cart with `+1` and `-1` marketplace-like controls.
- [x] Improved user management with blocking.
- [x] Review functionality.
- [x] Instant delivery (data + photo) for items from both cities.
- [x] Shipping address, shipping options and track numbers kept for legacy orders.
- [x] Multiple localization with i18n.
- [x] Referral system.
- [x] SQLAdmin web interface.
- [x] Interactive deployment script.
