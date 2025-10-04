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
@bot.command()
async def add(ctx, *, movie):
    if voting_locked:
        await ctx.send("Movie addition is locked!")
        return

    # Fuzzy duplicate check
    for existing_movie in movie_options:
        similarity = fuzz.ratio(movie.lower(), existing_movie.lower())
        if similarity > FUZZY_DUPLICATE_THRESHOLD: 
            await ctx.send(f"'{movie}' is too similar to '{existing_movie}' already in the list!")
            return

    movie_options.append(movie)
    await ctx.send(f"Added: {movie}")

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

@bot.command()
async def results(ctx):
    tally = [0] * len(movie_options)
    for user_votes in votes.values():
        for idx in user_votes:
            tally[idx] += 1
    
    results_msg = "Current vote tally:\n"
    for i, movie in enumerate(movie_options):
        results_msg += f"{movie}: {tally[i]} votes\n"
    
    await ctx.send(results_msg)

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
    embed.set_footer(text="Use !help <command> for more info on a specific command.")
    await ctx.send(embed=embed)

# Bot token
bot.run(BOT_TOKEN)
