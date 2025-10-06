import discord
from discord.ext import commands
from discord.ui import View, Button
from fuzzywuzzy import fuzz

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Config ---

MAX_VOTES_PER_USER = 3
FUZZY_DUPLICATE_THRESHOLD = 95 #similarity percentage for detecting duplicates
BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"

# --- Data ---
movie_options = []
voting_locked = False
votes = {}  # user_id: set of movie indices

# --- Commands ---

# Add item to list. 
# Can add as comma separated value
# Checks for dupicates using Fuzzywuzzy ratio threshold as defined and calibrated above with FUZZY_DUPLICATE_THRESHOLD
@bot.command()
async def add(ctx, *, movies):
    if voting_locked:
        await ctx.send("Movie addition is locked!")
        return

    added = []
    skipped = []

    # Split by comma and clean spaces
    movie_list = [m.strip() for m in movies.split(",") if m.strip()]

    for movie in movie_list:
        duplicate = False
        for existing_movie in movie_options:
            similarity = fuzz.ratio(movie.lower(), existing_movie.lower())
            if similarity > FUZZY_DUPLICATE_THRESHOLD:
                skipped.append(f"'{movie}' (too similar to '{existing_movie}')")
                duplicate = True
                break

        if not duplicate:
            movie_options.append(movie)
            added.append(movie)

    msg_parts = []
    if added:
        msg_parts.append(f"✅ Added: {', '.join(added)}")
    if skipped:
        msg_parts.append(f"⚠️ Skipped: {', '.join(skipped)}")

    await ctx.send("\n".join(msg_parts) if msg_parts else "No valid movies added.")

# Displays current items in developing list before voting
@bot.comamnd()
async def current(ctx):
    msg = "Current list:\n"
        for i, movie in enumerate(movie_options):
        results_msg += f"{movie}\n"
    
    await ctx.send(results_msg)

# Locks in list to be voted on. Displays buttons for voting and runs logic for voting
@bot.command()
async def lock(ctx):
    global voting_locked
    voting_locked = True
    if not movie_options:
        await ctx.send("Nothing to vote on!")
        return
    
    # Create buttons for each movie
    class MovieVoteView(View):
        def __init__(self):
            super().__init__(timeout=None)  # persistent view
            
            for i, movie in enumerate(movie_options):
                btn = Button(label=movie, style=discord.ButtonStyle.primary, custom_id=str(i))
                btn.callback = self.vote_callback
                self.add_item(btn)

        async def vote_callback(self, interaction: discord.Interaction):
            user_id = interaction.user.id
            movie_idx = int(interaction.data['custom_id'])
            user_votes = votes.get(user_id, set())
            
            if movie_idx in user_votes:
                await interaction.response.send_message("You already voted for this!", ephemeral=True)
                return

            if len(user_votes) >= MAX_VOTES_PER_USER:
                await interaction.response.send_message(f"You can only vote {MAX_VOTES_PER_USER} times!", ephemeral=True)
                return

            user_votes.add(movie_idx)
            votes[user_id] = user_votes
            await interaction.response.send_message(f"Your vote for **{movie_options[movie_idx]}** has been counted!", ephemeral=True)

    view = MovieVoteView()
    await ctx.send("Voting is now open!:", view=view)

# Output the current results of the voting. This does not clear the movie list.
# Fairly certain that "!lock" could be called again and a new round of voting on the same list
# could take place
@bot.command()
async def results(ctx):
    tally = [0] * len(movie_options)
    for user_votes in votes.values():
        for idx in user_votes:
            tally[idx] += 1

    # Combine movies with vote counts and sort descending by votes
    sorted_results = sorted(zip(movie_options, tally), key=lambda x: x[1], reverse=True)

    # align based on longest movie name
    longest_name = max(len(movie) for movie, _ in sorted_results)
    results_msg = "**Current vote tally:**\n```"

    for movie, count in sorted_results:
        results_msg += f"{movie.ljust(longest_name)} : {count} votes\n"

    results_msg += "```"
    await ctx.send(results_msg)


# Resets the list for a new list. 
# I somewhat want this to be called at the end of !results to automatically clear previous list, but 
# there may be some usecase to keep the old list relevent unless this is specifically called
@bot.command()
async def reset(ctx):
    global movie_options, votes, voting_locked
    if not voting_locked:
        await ctx.send("Voting is not currently locked.")
        return

    movie_options.clear()
    votes.clear()
    voting_locked = False
    await ctx.send("The voting poll has been reset. You can now add new movies.")

# Searches then removes item from the list. Single item only
@bot.command()
async def remove(ctx, *, movie_name):
    global movie_options, votes, voting_locked

    if voting_locked:
        await ctx.send("You cannot remove items after voting has started!")
        return

    # Case-insensitive search for the movie
    for i, movie in enumerate(movie_options):
        if movie.lower() == movie_name.lower():
            movie_options.pop(i)  # remove from the list
            
            # Remove votes for this movie from all users
            for user_id, user_votes in votes.items():
                user_votes.discard(i)
                # Also adjust indices greater than removed movie
                votes[user_id] = {v-1 if v > i else v for v in user_votes}

            await ctx.send(f"Removed '{movie}' from the list.")
            return

    await ctx.send(f"'{movie_name}' not found in the list.")

#While the list is not locked, the max votes per user can be adjusted with an integer input
@bot.command()
async def maxvotecount(ctx, maxvotesupdate):
    global MAX_VOTES_PER_USER

    if voting_locked:
        await ctx.send("You cannot update the maximum number of votes while the list is locked.")
        return

    if not maxvotesupdate.isdigit():
        await ctx.send("Please provide a valid integer for the maximum votes per user.")
        return

    MAX_VOTES_PER_USER = int(maxvotesupdate)
    await ctx.send(f"Max votes per user set to: {MAX_VOTES_PER_USER}")


# Outputs a list of the avaliable commands the user can call and their functionality
@bot.command()
async def commands(ctx):
    embed = discord.Embed(
        title="VoteBot Commands",
        description="Here are the commands you can use:",
        color=discord.Color.blurple()
    )
    embed.add_field(name="!add <name>", value="Adds a string to the list.", inline=False)
    embed.add_field(name="!lock", value="Locks the string list and starts voting.", inline=False)
    embed.add_field(name="!results", value="Shows the current vote tally.", inline=False)
    embed.add_field(name="!reset", value="Resets the voting poll.", inline=False)
    embed.add_field(name="!remove", value="Removes list item.", inline=False)
    embed.add_field(name="!maxvotecount", value="Updates maximum allowed votes per user.", inline=False)
    embed.set_footer(text="Use !help <command> for more info on a specific command.")
    await ctx.send(embed=embed)

# Bot token, Connects the bot to Discord
bot.run(BOT_TOKEN)
