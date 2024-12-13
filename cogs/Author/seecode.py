import discord
from discord.ext import commands
import os
import asyncio
import shutil

class BotManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.editing_code = False
        self.history = {}  # Stores version history for each file (undo)
        self.redo_history = {}  # Stores redo history

    def backup_file(self, filepath):
        """Creates a backup of the current file before modifying it."""
        if os.path.exists(filepath):
            if filepath not in self.history:
                self.history[filepath] = []
            # Read current file state and store in history for undo
            with open(filepath, "r", encoding="utf-8", errors="replace") as file:
                self.history[filepath].append(file.read())
                # Clear redo history upon new changes
                self.redo_history.pop(filepath, None)

    def restore_file(self, filepath, content):
        """Restores the content to the file."""
        with open(filepath, "w", encoding="utf-8", errors="replace") as file:
            file.write(content)

    @commands.command(name="showcode")
    @commands.is_owner()
    async def showcode(self, ctx, filepath: str):
        """Displays the content of a specified file."""
        if not os.path.exists(filepath):
            await ctx.send(f"File `{filepath}` not found.")
            return

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as file:
                code = file.read()

            for chunk in [code[i:i + 1990] for i in range(0, len(code), 1990)]:
                await ctx.send(f"```py\n{chunk}\n```")

        except FileNotFoundError:
            await ctx.send(f"File `{filepath}` not found.")
        except PermissionError:
            await ctx.send(f"Permission denied for reading file `{filepath}`.")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")

    @commands.command(name="editcode")
    @commands.is_owner()
    async def editcode(self, ctx, filepath: str):
        """Enters editing mode for a specific file."""
        if self.editing_code:
            await ctx.send("Already in editing mode. Please finish the current edit before starting a new one.")
            return

        if not os.path.exists(filepath):
            await ctx.send(f"File `{filepath}` not found.")
            return

        self.editing_code = True
        self.backup_file(filepath)  # Save current state for undo
        await ctx.send(f"Editing `{filepath}`. Reply with the new content, or type `cancel` to exit.")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            user_message = await self.bot.wait_for("message", check=check, timeout=300.0)
            
            if user_message.content.lower() == "cancel":
                self.editing_code = False
                await ctx.send("Edit mode cancelled.")
                return

            try:
                with open(filepath, "w", encoding="utf-8", errors="replace") as file:
                    file.write(user_message.content)
                await ctx.send(f"Changes saved to `{filepath}`.")
            except FileNotFoundError:
                await ctx.send(f"File `{filepath}` not found.")
            except PermissionError:
                await ctx.send(f"Permission denied for writing to file `{filepath}`.")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while saving the file: {e}")

        except asyncio.TimeoutError:
            await ctx.send("Timed out, exiting edit mode.")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
        finally:
            self.editing_code = False

    @commands.command(name="uploadcode")
    @commands.is_owner()
    async def uploadcode(self, ctx, filepath: str):
        """Allows the owner to upload a file and save it to a specified filepath, overwriting its contents."""
        if not os.path.exists(filepath):
            await ctx.send(f"File `{filepath}` does not exist. I will create it after uploading the file.")
        
        await ctx.send(f"Please upload the file that will replace `{filepath}`.")
        self.backup_file(filepath)  # Save current state for undo

        def check_file(m):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.attachments) > 0

        try:
            user_message = await self.bot.wait_for("message", check=check_file, timeout=120.0)

            attachment = user_message.attachments[0]

            # Check file size
            if attachment.size > 8 * 1024 * 1024:  # 8MB limit for attachments
                await ctx.send("File size exceeds the 8MB limit.")
                return

            try:
                # Overwrite the contents of the existing file with the uploaded file
                await attachment.save(filepath)
                await ctx.send(f"File `{attachment.filename}` has been uploaded and saved as `{filepath}`, overwriting the previous content.")
            except PermissionError:
                await ctx.send(f"Permission denied for saving file to `{filepath}`.")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while saving the file: {e}")

        except asyncio.TimeoutError:
            await ctx.send("File upload timed out.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to download file: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")

    @commands.command(name="revertcode")
    @commands.is_owner()
    async def revertcode(self, ctx, filepath: str):
        """Reverts the file to its previous version."""
        if filepath not in self.history or not self.history[filepath]:
            await ctx.send(f"No previous versions available for `{filepath}`.")
            return

        # Backup current version for redo
        with open(filepath, "r", encoding="utf-8", errors="replace") as file:
            current_content = file.read()

        if filepath not in self.redo_history:
            self.redo_history[filepath] = []

        self.redo_history[filepath].append(current_content)

        # Restore last saved version
        last_version = self.history[filepath].pop()
        self.restore_file(filepath, last_version)

        # Send confirmation with the first and last lines of the new file
        first_line = last_version.splitlines()[0] if last_version.splitlines() else "Empty"
        last_line = last_version.splitlines()[-1] if last_version.splitlines() else "Empty"
        await ctx.send(f"File `{filepath}` has been reverted.\nNow the code begins with:\n```{first_line}```\nAnd ends with:\n```{last_line}```")

    @commands.command(name="reverserevertcode")
    @commands.is_owner()
    async def reverserevertcode(self, ctx, filepath: str):
        """Re-applies the last reverted changes (redo)."""
        if filepath not in self.redo_history or not self.redo_history[filepath]:
            await ctx.send(f"No reverted versions available to redo for `{filepath}`.")
            return

        # Reapply the last reverted version
        last_redo_version = self.redo_history[filepath].pop()
        self.restore_file(filepath, last_redo_version)

        # Send confirmation with the first and last lines of the new file
        first_line = last_redo_version.splitlines()[0] if last_redo_version.splitlines() else "Empty"
        last_line = last_redo_version.splitlines()[-1] if last_redo_version.splitlines() else "Empty"
        await ctx.send(f"File `{filepath}` has been restored (redo).\nNow the code begins with:\n```{first_line}```\nAnd ends with:\n```{last_line}```")

    @commands.command(name="showfiles")
    @commands.is_owner()
    async def showfiles(self, ctx, root_dir: str = ".", max_depth: int = 3):
        """Shows a clean, formatted view of the bot's files and folders, split into multiple messages if necessary,
        excluding __pycache__, image-related folders, and image files."""

        image_extensions = (".png", ".jpeg", ".jpg", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico")

        def list_directory(directory, level=0):
            """Recursively lists directories and files with indentation, excluding __pycache__ folders,
            image-related folders, .pyc files, and image files."""
            if level >= max_depth:
                return ""
            blueprint = ""
            items = sorted(os.listdir(directory))  # Sort alphabetically
            for item in items:
                item_path = os.path.join(directory, item)

                # Skip __pycache__, image-related folders, .pyc files, and image files
                if ("__pycache__" in item or "images" in item.lower() or
                        item.endswith(".pyc") or item.lower().endswith(image_extensions)):
                    continue

                if os.path.isdir(item_path):
                    blueprint += "📁 " + " " * (level * 2) + f"{item}/\n"
                    blueprint += list_directory(item_path, level + 1)
                else:
                    blueprint += "📄 " + " " * (level * 2) + f"{item}\n"
            return blueprint

        if not os.path.exists(root_dir):
            await ctx.send(f"Directory `{root_dir}` does not exist.")
            return

        try:
            directory_structure = list_directory(root_dir)
            if not directory_structure:
                await ctx.send(f"The directory `{root_dir}` is empty or too deep to display.")
                return

            # Split the directory structure into chunks of 1990 characters to stay within the Discord message limit.
            chunks = [directory_structure[i:i + 1990] for i in range(0, len(directory_structure), 1990)]
            for chunk in chunks:
                await ctx.send(f"```\n{chunk}\n```")

        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")

    @commands.command(name="deletefile")
    @commands.is_owner()
    async def deletefile(self, ctx, path: str):
        """Deletes a specified file or folder."""
        if not os.path.exists(path):
            await ctx.send(f"File or directory `{path}` does not exist.")
            return

        try:
            if os.path.isfile(path):
                os.remove(path)
                await ctx.send(f"File `{path}` deleted successfully.")
            elif os.path.isdir(path):
                shutil.rmtree(path)
                await ctx.send(f"Directory `{path}` deleted successfully.")
            else:
                await ctx.send(f"`{path}` is not a valid file or directory.")
        except Exception as e:
            await ctx.send(f"An error occurred while trying to delete `{path}`: {e}")

    @commands.command(name="createfile")
    @commands.is_owner()
    async def createfile(self, ctx, path: str):
        """Creates a new empty file at the specified path."""
        if os.path.exists(path):
            await ctx.send(f"A file or directory already exists at `{path}`.")
            return

        try:
            with open(path, 'w') as file:
                pass  # Just create an empty file
            await ctx.send(f"File `{path}` created successfully.")
        except Exception as e:
            await ctx.send(f"An error occurred while creating the file: {e}")

    @commands.command(name="createfolder")
    @commands.is_owner()
    async def createfolder(self, ctx, path: str):
        """Creates a new folder at the specified path."""
        if os.path.exists(path):
            await ctx.send(f"A file or directory already exists at `{path}`.")
            return

        try:
            os.makedirs(path)
            await ctx.send(f"Folder `{path}` created successfully.")
        except Exception as e:
            await ctx.send(f"An error occurred while creating the folder: {e}")


    @commands.command(name="renamefile")
    @commands.is_owner()
    async def renamefile(self, ctx, old_path: str, new_name: str):
        """Renames a specified file or folder."""
        if not os.path.exists(old_path):
            await ctx.send(f"File or directory {old_path} does not exist.")
            return

        new_path = os.path.join(os.path.dirname(old_path), new_name)

        try:
            os.rename(old_path, new_path)
            await ctx.send(f"{old_path} renamed to {new_name}.")
        except Exception as e:
            await ctx.send(f"An error occurred while renaming {old_path}: {e}")

    @commands.command(name="placefile")
    @commands.is_owner()
    async def placefile(self, ctx, source: str, destination: str):
        """Moves a file or folder to a new location."""
        if not os.path.exists(source):
            await ctx.send(f"File or directory {source} does not exist.")
            return

        # Ensure the destination directory exists
        dest_dir = os.path.dirname(destination)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        try:
            shutil.move(source, destination)
            await ctx.send(f"{source} has been moved to {destination}.")
        except Exception as e:
            await ctx.send(f"An error occurred while moving {source}: {e}")

async def setup(bot):
    await bot.add_cog(BotManager(bot))
