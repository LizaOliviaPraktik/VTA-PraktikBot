# IMPORTING LIBRARIES
import os
# Reading from env file
from dotenv import load_dotenv
import openai
import discord
from discord.ext import commands
# Handling asynchronous functions
import asyncio
# Used for fetching data from Azure Search
import requests

# Loading variables from env. file
load_dotenv()

"""
print("API_KEY:", os.getenv("AZURE_OPENAI_API_KEY"))
print("DISCORD_TOKEN:", os.getenv("DISCORD_TOKEN"))
"""

# Setting up Discord intents so bot knows what it has access to
# Accessing: messages
intents = discord.Intents.default()
intents.message_content = True

# APi keys and endpoints
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") 
OPENAI_API_VERSION = "2024-07-01-preview"

AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")

# Configuring OpenAI API from Azure
# Important to emphasize "azure" so it does not mix up with OpenAi:s API
openai.api_type = "azure"
openai.api_base = AZURE_OPENAI_ENDPOINT
openai.api_key = AZURE_OPENAI_API_KEY
openai.api_version = OPENAI_API_VERSION

# Parameter: query = user search prompt
def search_documents(query):
    # URL to search thorugh Azure Search index
    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX_NAME}/docs?api-version=2023-07-01-preview&search={query}"
    # API key and explaining that JSON-data is used
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_API_KEY}

    try:
        # Retrieving values(headers) from the correlated key(url)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        # Important to recieve the result as json!
        results = response.json()

        if "value" in results:
            # top 3 documents will be fetched if results is found
            top_docs = "\n\n".join([doc["content"] for doc in results["value"][:3]])
            return top_docs if top_docs else "Inga relevanta dokument hittades."
        else:
            return "Inga relevanta dokument hittades."

    # Error handling
    except requests.exceptions.RequestException as e:
        print(f"Azure Search Error: {str(e)}")
        return "Kunde inte hämta relevanta dokument."

# Class: ChatGPTBot, inherits from commands.Bot so it can handles commando's
class ChatGPTBot(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
        # To store message history (that way the bot will remember what has been said before)
        self.message_history = [] 

    # Asynchronous function which executes when the bot has launched and is online
    async def on_ready(self):
        print(f"{self.user} är nu online och redo att svara!")

    async def on_message(self, message):
        # Ignores messages from itself
        if message.author == self.user:
            return

        # Fetching users query = message content, and searching with Azure Search to fetch relevant documents
        query = message.content
        relevant_text = search_documents(query)

        # Storing conversation history and creating system prompt
        self.message_history = [
        {
            "role": "system",
            "content": (
                "Du är en AI-assistent som ska hjälpa studenter att hitta svar baserat på information "
                "som tillhandahålls från en databas. Du får endast ge information som framgår i dokumenten "
                "och måste undvika spekulation eller information utanför det givna materialet.\n\n"
                "## Instruktioner:\n"
                "- Svara på studentens frågor enbart med information hämtad från de tillhandahållna dokumenten.\n"
                "- Sträva efter att vägleda studenten genom att ge ledtrådar eller förklarande steg utan att ge "
                "direkta svar förrän minst tre omgångar av vägledning har getts.\n"
                "- Om svaret överstiger 2000 tokens, meddela studenten att svaret är för långt och avsluta.\n\n"
                "# Principer:\n"
                "1. **Databasspecifik**: Begränsa svaren till information som finns i de tillhandahållna dokumenten.\n"
                "2. **Ingen spekulation**: Undvik att svara med information utanför det givna materialet.\n"
                "3. **Vägledande svar**: Undvik att ge ett direkt svar i början. Fokusera istället på att guida studenten "
                "genom att uppmuntra till reflektion och utforska relevanta delar av materialet.\n"
                "4. **Tokenbegränsning**: Om en fråga kräver mer än 2000 tokens för att svara på komplett måste du ange "
                "att svaret är för långt och avsluta utan att ge fullständig information.\n\n"
                "## Hämtad information:\n"
                f"{relevant_text}\n\n"
                "# Output Format:\n"
                "- **Vägledande Faser**: Tre steg av vägledning utan att ge ett direkt svar. Varje del ska vara kort "
                "och främja studentens reflektion.\n"
                "- **Slutgiltig Fas**: Efter tre vägledande faser kan en sammanfattning eller mer direkt information "
                "tillhandahållas, utan att överskrida tokenbegränsningen.\n"
                "- Om svaret är för långt: Skriv 'Svaret är för långt för att hanteras i denna konversation.'"
            ),
        },
        {"role": "user", "content": query},
    ]

        try:
            # Sending request to OpenAi:s API to generate answer
            chat_response = openai.ChatCompletion.create(
                engine=AZURE_OPENAI_DEPLOYMENT, 
                messages=self.message_history  
            )

            # Extracting responses from OpenAI's and sending it to the user
            chat_message = chat_response["choices"][0]["message"]["content"]
            await message.channel.send(chat_message)

            # Appending to history list
            self.message_history.append({"role": "assistant", "content": chat_message})

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            await message.channel.send("Jag stötte på ett fel. Försök igen senare.")

        await self.process_commands(message)

# Creating and starting the bot (is online)
async def main():
    bot = ChatGPTBot(command_prefix="!", intents=intents)
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())


#To run type in terminal: python chatgpt_bot.py
