# Urge Discord Bot

A fully-featured, custom, all-in-one Discord Bot built specifically for managing server operations including Support Tickets, Staff Applications, Automod, Giveaways, Vouches, and Leveling.

## 🚀 Features

### 1. Unified Setup Menu
- Use `/setup` to spawn interactive dropdown menus for setting up various server panels and configuring channels.
- Available Panels: **Support Tickets**, **Spawner Trading**, **Partnership Requirements**, **Ban Appeals**, **Schematic Service**, **Vouches**, and **Staff Applications**.
- Configuration Options: Set the Welcome channel, Levelup channel, and Staff Apps Review channel.

### 2. Automod & Chat Filter
- Advanced banned words filter using Regex.
- Automatically catches spaced-out characters (e.g., `w o r d`).
- **Penalties**: Deletes the message and automatically times out the user for **1 hour** (applies to all users, including Administrators).
- Use `/filter list`, `/filter add <word>`, and `/filter remove <index>` to manage the word list in real-time.

### 3. Staff Applications
- Applicants click the panel button to begin an interactive **DM interview**.
- The bot asks questions one-by-one with a 1-hour timeout per question.
- Finished applications are sent to a designated review channel.
- **Admin Review Buttons**: Administrators can click `✅ Approve` or `❌ Deny` directly on the application embed. Approving automatically assigns the correct role and notifies the user!

### 4. Leveling & Rank System
- Users gain XP randomly between 15-25 per message (1-minute cooldown).
- Milestone rank cards are posted to the Levelup channel every 5 levels.
- `/levels [member]`: View a custom-generated Yellow Rank Card with your PFP and progress bar.
- `/rank`: View the server's leveling leaderboard.

### 5. Vouch System
- Users can leave vouches via the interactive Vouch Panel or `/vouch add <target>`.
- 10-minute cooldown on submitting vouches to prevent spam.
- `/vouch stats`: View the top vouched members.
- `/vouch user [member]`: View vouch counts for specific users.

### 6. Giveaways & Proofs
- `/gcreate`: Create a giveaway using a clean UI modal.
- `/greroll`: Reroll a winner.
- `/gstats stats` and `/gstats user`: Track giveaway metrics.
- `/proof`: Upload a proof image when closing a ticket.

### 7. Moderation
- `/slowmode set <delay>` and `/slowmode remove`: Manage channel slowmode easily.
- `/ban <member>`: Instantly strips all roles and assigns the Banned role to restrict access.
- `/unban <member>`: Removes the Banned role and restores access.

## ⚙️ Configuration & Setup

1. Copy `.env.example` to `.env`.
2. Fill in your `DISCORD_TOKEN` and the necessary Channel/Category/Role IDs.
3. Install dependencies using `pip install -r requirements.txt`.
4. Run the bot using `python bot.py`.

*Note: All persistent data like levels, vouches, banned words, and server config are automatically saved and loaded from the `data/` folder in `.json` format.*
