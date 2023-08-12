import nextcord, json, collections, os.path#, datetime, re
#from datetime import datetime
from nextcord.ext import commands
from nextcord.ui import Select, Button, View

#autoSlot Cog
class autoSlot(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.database = {'operations' : {}}
        self.roster_category = None

    @commands.Cog.listener()
    async def on_ready(self):
        #Check and load pre-existing JSON
        if os.path.exists('autoSlot.json'):
            with open('autoSlot.json', 'r') as json_file:
                self.database = json.load(json_file)

    @commands.command(name = "addoperation", help = "Adds a new operation with given name. Use quotations for multi-word names", aliases=["addop","ao"])
    @commands.has_any_role("Operations Command", "Command Consultant", "Campaign Host", "Operation Host")
    async def addOperation(self, ctx, operation_name: str, operation_timestamp: int):

        # Set Bot Commands as output channel
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        operation_id = 1
        while operation_id < 1000:
            if str(operation_id) not in self.database['operations'] :
                break
            else:
                operation_id += 1

        # Make channel name that is compatible with discord's channel restrictions
        exceptioncharacters = ["!","@","#","$","%","^","&","*","(",")","=","+","|","[","]","{","}","`","~",'"',"'","/","?",",","<",">",".",";",":"]
        operation_name_converted = operation_name.replace(" ", "-").lower()
        for character in exceptioncharacters:
            operation_name_converted = operation_name_converted.replace(character, "")

        # Warn user that operation name is converted for discord channel restrictions
        if (operation_name != operation_name_converted):
            await botCommandsChannel.send(f"{ctx.author.mention} Your operation's channel will be renamed from {operation_name} to {operation_name_converted}")

        #Warn user if there are more than 10 operations in database
        if len(self.database['operations']) > 10:
            await botCommandsChannel.send("There are currently 10 active operations on ID's 1-10. Please delete old operations.")
            #return

        # Add operation to database
        self.database['operations'].update({str(operation_id) : {'groups' : {}, 'assignments' : {}, 'channel_name' : operation_name_converted, 'name' : operation_name,'author' : ctx.author.id, 'operation_timestamp' : operation_timestamp} })
        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.author.mention} has added a new operation. Your operation ID for {operation_name_converted} is: {operation_id}")

    @commands.command(name = "addslots")
    @commands.has_any_role("Operations Command", "Command Consultant", "Campaign Host", "Operation Host")
    async def addSlots(self, ctx, operation_id, *, slots):

        # Set Bot Commands as output channel
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        # Check if operation ID exists
        try:
            if operation_id not in self.database['operations']:
                return await botCommandsChannel.send("There is no operation present in the database with this ID.")
        except:
            return await botCommandsChannel.send("A problem occured with the operation id.")

        # Parse slots into a list of the groups and a dictionary of all the slots
        group_list, group_dict = self.parseStringToGroups(slots)

        # Check parse was successful
        if group_list is False:
            return await botCommandsChannel.send("Your request did not match the required formatting, please check your input for issues.")

        # Save groups to database under specific operation id
        #self.database = self.updateDict(self.database, {'operations' : {operation_id : {'groups' : group_dict}}})
        self.database['operations'][operation_id]['groups'] = group_dict

        # Look for the self.roster_category and roster_channel
        roster_channel = None
        channel_name = self.database['operations'][operation_id]['channel_name']

        # Look for roster category. If it doesnt exist, create it
        for category in ctx.guild.categories:
            if category.name == 'rosters':
                self.roster_category = category
                break

        # If no self.roster_category is found, create it
        if self.roster_category == None:
            self.roster_category = await ctx.guild.create_category('rosters')

        # Once created, look for the operation channel. Otherwise, create it
        for channel in self.roster_category.channels:
            if channel.name == (f"{operation_id}-{channel_name}"):
                roster_channel = channel
                break

        # Post the roster
        # If channel doesnt exist, make the channel and post the first roster in it
        if roster_channel == None:
            roster_channel = await self.roster_category.create_text_channel(f'{operation_id}-{channel_name}')

        # Parse groups into an embed roster
        embed_roster_message = self.embedGroupsToRoster(ctx, operation_id, group_list)
        if embed_roster_message == None:
            #TODO: Move slotname checking to parseStringToGroups instead of embedGroupsToRoster
            self.database['operations'][operation_id]['groups'] = {}
            return await botCommandsChannel.send("Please limit the length of a slotname to 25, the number of slots in a single group to 20, and the number of groups to 10.")
        view = View(timeout=None)
        if len(self.database['operations'][operation_id]['groups']) > 1:
            firstgroup, *_, lastgroup = self.database['operations'][operation_id]['groups'].keys()
            if len(self.database['operations'][operation_id]['groups'][lastgroup].keys()) > 1:
                firstslot, *_, lastslot = self.database['operations'][operation_id]['groups'][lastgroup].keys()
            else:
                *_, lastslot = self.database['operations'][operation_id]['groups'][lastgroup].keys()
        else:
            *_, lastgroup = self.database['operations'][operation_id]['groups'].keys()
            if len(self.database['operations'][operation_id]['groups'][lastgroup].keys()) > 1:
                firstslot, *_, lastslot = self.database['operations'][operation_id]['groups'][lastgroup].keys()
            else:
                *_, lastslot = self.database['operations'][operation_id]['groups'][lastgroup].keys()
                
        if int(lastslot) >= 26:
            await ctx.send("Mission is over 25 slots, no select menu will be available.")
        else:
            dropdownroles = []
            for group in group_list:
                slot_dict = self.database['operations'][operation_id]['groups'][group]
                for slot in slot_dict:
                    desc = ""
                    slotlabel = f"{slot}: {self.database['operations'][operation_id]['groups'][group][slot]}"
                    desc = group
                    dropdownroles.append(nextcord.SelectOption(label=slotlabel, description=desc, value=slot))
            dropdown = Select(placeholder="Reserve role", options=dropdownroles)
            async def dropdownbackend(ctx):
                await ctx.response.defer()
                await self.iaslot(ctx=ctx, slot_id=dropdown.values[0])
                return
            dropdown.callback = dropdownbackend
            view.add_item(dropdown)
            async def buttonbackend(ctx):
                await ctx.response.defer()
                await self.irslot(ctx=ctx)
            rslotbutton = Button(label="Unslot", style=nextcord.ButtonStyle.danger)
            rslotbutton.callback = buttonbackend
            view.add_item(rslotbutton)
            

        # If previous roster exists, edit it with the embed_roster_message
        if await roster_channel.history().get(author__id = self.client.user.id):
            previous_roster_message = await roster_channel.history().get(author__id = self.client.user.id)
            await previous_roster_message.edit(embed=embed_roster_message, view=view)
        # Else, just send the embed_roster_message
        else:
            await roster_channel.send(embed=embed_roster_message, view=view)

        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.author.mention} has added slots to {self.database['operations'][operation_id]['channel_name']}.")

    @commands.command(aliases=['assignslot','takeslot', 'claimslot', 'cslot', 'tslot','slot','role'])
    async def aslot(self, ctx, slot_id, target=None):

        # Determine Op ID by channel name
        operation_id = str(ctx.channel)[0]

        # Set Bot Commands as output channel
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        # Delete User Message before Update
        try:
            await ctx.message.delete()
        except:
            print()

        # Check target user if they exist
        if target:
            # If author is not a host, stop execution
            if (len([x for x in ctx.author.roles if x in ["Operations Command", "Command Consultant", "Campaign Host", "Operation Host"]]) > 0):
                 return await botCommandsChannel.send(f'{ctx.author.mention} is not a host. Only hosts can assign another operative to a slot.')
            # Check if target user exists
            if ctx.author == None:
                await botCommandsChannel.send(f"Failed to find user {ctx.author}.")
            # Find and set ctx.author to target
            ctx.author = ctx.guild.get_member(int(target.translate({ord(i): None for i in '@<>'})))

        # Check if operation exists
        if self.database['operations'].get(operation_id) == None:
            return await botCommandsChannel.send(f"Operation ID {operation_id} not found.")

        # Pull list of groups and dictionary of roles
        group_list =[]
        slot_dict = {}
        for group in self.database['operations'][operation_id]['groups']:
            group_list.append(group)
            slot_dict.update(self.database['operations'][operation_id]['groups'][group])

        # Check if slot exists
        if slot_dict.get(slot_id) == None:
            return await botCommandsChannel.send(f"Slot ID {slot_id} not found.")
        
        # Check if slot already has user

        if self.database['operations'][operation_id]['assignments'].get(slot_id):
            return await botCommandsChannel.send("Please remove the person from this slot before trying to claim it.")
        
       

        # Check if user already has a slot, (and the slot exists, and the slot doesnt already have a user from the checks above)
        for slot in self.database.copy()['operations'][operation_id]['assignments']:
            if ctx.author.id == self.database['operations'][operation_id]['assignments'].get(slot):
                del self.database['operations'][operation_id]['assignments'][slot]
                break

        # Check if user already has a slot
        for slot in self.database['operations'][operation_id]['assignments']:
            if ctx.author.id == self.database['operations'][operation_id]['assignments'].get(slot):
                return await botCommandsChannel.send(f"{ctx.author.mention} can only claim one slot at a time.")

        # Update database with new assignment
        #self.database = self.updateDict(self.database, {'operations' : {operation_id : {'assignments' : {slot_id : user.id}}}})
        self.database['operations'][operation_id]['assignments'][slot_id] = ctx.author.id

        # Check if roster_category exists, otherwise create it
        for category in ctx.guild.categories:
            if category.name == 'rosters':
                self.roster_category = category
                break
        if self.roster_category == None:
            return await botCommandsChannel.send("No channel can be found for this operation can be found. Have roles been added yet?")

        # Edit embed 
        roster_channel = nextcord.utils.get(ctx.guild.channels, name=f"{operation_id}-{self.database['operations'][operation_id]['channel_name']}", category=self.roster_category)
        message = await roster_channel.history().get(author__id = self.client.user.id)
        await message.edit(embed=self.embedGroupsToRoster(ctx, operation_id, group_list))
        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.author.mention} has taken slot {slot_id} in {self.database['operations'][operation_id]['channel_name']}.")

    #INTERACTION COMPATIBLE ASLOT
    async def iaslot(self, ctx, slot_id, target=None):

        # Determine Op ID by channel name
        operation_id = str(ctx.channel)[0]

        # Set Bot Commands as output channel
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        # Check if operation exists
        if self.database['operations'].get(operation_id) == None:
            return await botCommandsChannel.send(f"Operation ID {operation_id} not found.")

        # Pull list of groups and dictionary of roles
        group_list =[]
        slot_dict = {}
        for group in self.database['operations'][operation_id]['groups']:
            group_list.append(group)
            slot_dict.update(self.database['operations'][operation_id]['groups'][group])

        # Check if slot exists
        if slot_dict.get(slot_id) == None:
            return await botCommandsChannel.send(f"Slot ID {slot_id} not found.")
        
        # Check if slot already has user

        if self.database['operations'][operation_id]['assignments'].get(slot_id):
            return await botCommandsChannel.send("Please remove the person from this slot before trying to claim it.")
        
       

        # Check if user already has a slot, (and the slot exists, and the slot doesnt already have a user from the checks above)
        for slot in self.database.copy()['operations'][operation_id]['assignments']:
            if ctx.user.id == self.database['operations'][operation_id]['assignments'].get(slot):
                del self.database['operations'][operation_id]['assignments'][slot]
                break

        # Check if user already has a slot
        for slot in self.database['operations'][operation_id]['assignments']:
            if ctx.user.id == self.database['operations'][operation_id]['assignments'].get(slot):
                return await botCommandsChannel.send(f"{ctx.author.mention} can only claim one slot at a time.")

        # Update database with new assignment
        #self.database = self.updateDict(self.database, {'operations' : {operation_id : {'assignments' : {slot_id : user.id}}}})
        self.database['operations'][operation_id]['assignments'][slot_id] = ctx.user.id

        # Check if roster_category exists, otherwise create it
        for category in ctx.guild.categories:
            if category.name == 'rosters':
                self.roster_category = category
                break
        if self.roster_category == None:
            return await botCommandsChannel.send("No channel can be found for this operation can be found. Have roles been added yet?")

        # Edit embed 
        roster_channel = nextcord.utils.get(ctx.guild.channels, name=f"{operation_id}-{self.database['operations'][operation_id]['channel_name']}", category=self.roster_category)
        message = await roster_channel.history().get(author__id = self.client.user.id)
        await message.edit(embed=self.embedGroupsToRoster(ctx, operation_id, group_list))
        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.user.mention} has taken slot {slot_id} in {self.database['operations'][operation_id]['channel_name']}.")

    @commands.command(aliases=['deleteslot','delslot','removeslot','rmslot'])
    async def rslot(self, ctx, slot_id=None):

        # Determine Op ID by channel name
        operation_id = str(ctx.channel)[0]

        # Set Bot Commands as output channel
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        # Delete User Message before Update
        try:
            await ctx.message.delete()
        except:
            print()

        # Check if operation exists
        if self.database['operations'].get(operation_id) == None:
            return await botCommandsChannel.send(f"Operation ID {operation_id} not found.")

        # Pull list of groups and dictionary of roles
        group_list =[]
        slot_dict = {}
        for group in self.database['operations'][operation_id]['groups']:
            group_list.append(group)
            slot_dict.update(self.database['operations'][operation_id]['groups'][group])
        
        if slot_id != None:
            # Check if slot exists
            if slot_dict.get(slot_id) == None:
                return await botCommandsChannel.send("Slot not found.") 

        if slot_id != None and self.database['operations'][operation_id]['assignments'].get(slot_id) != ctx.author.id:
            if "Campaign Host" in ctx.author.roles or "Operations Command" in ctx.author.roles or "Command Consultant" in ctx.author.roles or "Operation Host" in ctx.author.roles:
                return await botCommandsChannel.send('You are not a host. Only hosts can remove another operative from a slot.')
            del self.database['operations'][operation_id]['assignments'][slot_id]
        else:
            # Find user slot
            for slot in self.database['operations'][operation_id]['assignments']:
                if ctx.author.id == self.database['operations'][operation_id]['assignments'].get(slot):
                    slot_id = slot
                    break
            else:
                await botCommandsChannel.send("Slot not found.")
            del self.database['operations'][operation_id]['assignments'][slot_id]

        # Check if roster_category exists, otherwise create it
        for category in ctx.guild.categories:
            if category.name == 'rosters':
                self.roster_category = category
                break
        if self.roster_category == None:
            return await botCommandsChannel.send("No channel for this operation can be found. Have roles been added yet?")
        
        # Edit embed 
        roster_channel = nextcord.utils.get(ctx.guild.channels, name=f"{operation_id}-{self.database['operations'][operation_id]['channel_name']}", category=self.roster_category)
        message = await roster_channel.history().get(author__id = self.client.user.id)
        await message.edit(embed=self.embedGroupsToRoster(ctx, operation_id, group_list))
        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.author.mention} has removed a user from slot {slot_id} in {self.database['operations'][operation_id]['channel_name']}.")

    #INTERACTION COMPATIBLE RSLOT
    async def irslot(self, ctx, slot_id=None):
        # Determine Op ID by channel name
        operation_id = str(ctx.channel)[0]

        # Set Bot Commands as output channel
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        # Delete User Message before Update
        
        # Check if operation exists
        if self.database['operations'].get(operation_id) == None:
            return await botCommandsChannel.send(f"Operation ID {operation_id} not found.")

        # Pull list of groups and dictionary of roles
        group_list =[]
        slot_dict = {}
        for group in self.database['operations'][operation_id]['groups']:
            group_list.append(group)
            slot_dict.update(self.database['operations'][operation_id]['groups'][group])

        # Find user slot
        for slot in self.database['operations'][operation_id]['assignments']:
            if ctx.user.id == self.database['operations'][operation_id]['assignments'].get(slot):
                slot_id = slot
                break
        else:
            return
        del self.database['operations'][operation_id]['assignments'][slot_id]

        # Check if roster_category exists, otherwise create it
        for category in ctx.guild.categories:
            if category.name == 'rosters':
                self.roster_category = category
                break
        if self.roster_category == None:
            return await botCommandsChannel.send("No channel for this operation can be found. Have roles been added yet?")
        
        # Edit embed 
        roster_channel = nextcord.utils.get(ctx.guild.channels, name=f"{operation_id}-{self.database['operations'][operation_id]['channel_name']}", category=self.roster_category)
        message = await roster_channel.history().get(author__id = self.client.user.id)
        await message.edit(embed=self.embedGroupsToRoster(ctx, operation_id, group_list))
        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.user.mention} has removed themself from slot {slot_id} in {self.database['operations'][operation_id]['channel_name']}.")


    
    @commands.command(aliases=['deleteslotall','delslotall','removeslotall','rmslotall','deleteallslots','delallslots','removeallslots','rmallslots'])
    @commands.has_any_role("Operations Command", "Command Consultant", "Campaign Host", "Operation Host")
    async def rslotAll(self, ctx):

        # Determine Op ID by channel name
        operation_id = str(ctx.channel)[0]

        # Determine Op ID by channel name
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        # Delete User Message before Update
        try:
            await ctx.message.delete()
        except:
            print()

        # Check if operation exists
        if self.database['operations'].get(operation_id) == None:
            return await botCommandsChannel.send(f"Operation ID {operation_id} not found.")

        # Pull list of groups and dictionary of roles
        group_list =[]
        #slot_dict = {}
        for group in self.database['operations'][operation_id]['groups']:
            group_list.append(group)
            #slot_dict.update(self.database['operations'][operation_id]['groups'][group])

        # Reset assignments to empty
        self.database['operations'][operation_id]['assignments'] = {}

        # Check if roster_category exists, otherwise create it
        for category in ctx.guild.categories:
            if category.name == 'rosters':
                self.roster_category = category
                break
        if self.roster_category == None:
            return await botCommandsChannel.send("No channel can be found for this operation can be found. Have roles been added yet?")

        # Edit embed 
        roster_channel = nextcord.utils.get(ctx.guild.channels, name=f"{operation_id}-{self.database['operations'][operation_id]['channel_name']}", category=self.roster_category)
        message = await roster_channel.history().get(author__id = self.client.user.id)
        await message.edit(embed=self.embedGroupsToRoster(ctx, operation_id, group_list))
        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.author.mention} removed all operatives from {self.database['operations'][operation_id]['channel_name']}.")

    @commands.command()
    @commands.has_any_role("Operations Command", "Command Consultant", "Campaign Host", "Operation Host")
    async def feedback(self, ctx, operation_id=None):
        # Determine Op ID by channel name
        if operation_id == None:
            operation_id = str(ctx.channel)[0]
        else:
            operation_id = str(operation_id)
        # Find the feedback channel and then create a thread for the operation
        feedbackChannel = nextcord.utils.get(ctx.guild.channels, name=f"operation-feedback")
        thread = await feedbackChannel.create_thread(name=f"{self.database['operations'][operation_id]['name']} Feedback", message=None, auto_archive_duration=60, type=nextcord.ChannelType.public_thread, reason=None)
        '''
        Retrieve the assignments for given operation ID and construct a "silentping"
        The "silentping" variable is a string constructed by a for-loop with the discord member.mention objects for each member present in the roster.
        The first stage iterates through the members in the assignment list, and adds their member.mention objects to the string.
        If the mission roster is not empty, a dummy message will be sent and then edited with the "silentping" variable. Since the message was edited
        with the member.mention objects, rather than sent with them, the mentioned members will be added to the thread without actually being "pinged" by discord.
        The message will then be immediately deleted for cleanliness and to create the illusion that no one was ever pinged.
        '''
        assignments = self.database['operations'][operation_id]['assignments']
        silentping = ""
        for member in assignments:
            silentping += f" {ctx.guild.get_member(assignments.get(member)).mention}"
        if silentping != "":  
            mention_message = await thread.send("About to ping members.")
            await mention_message.edit(silentping)
            await mention_message.delete()
        # If there is a squad leader on the roster, they will be mentioned along with the host in the first message /visible/ in the channel by the time anyone gets to it.
        # (Since the silentping message was already deleted by this point.)
        if assignments.get('1') == None:
            await thread.send(f"Feedback for Host: {ctx.guild.get_member(self.database['operations'][operation_id]['author']).mention} \nGive a number out of ten. \nLeave feedback for leadership as well.")
        else:
            await thread.send(f"Feedback for Host: {ctx.guild.get_member(self.database['operations'][operation_id]['author']).mention} \nGive a number out of ten. \nFeedback for leadership: {ctx.guild.get_member(assignments.get('1')).mention}")

    # Remove operation
    @commands.command(aliases=['deloperation','delop','removeoperation','rmoperation','rmop'])
    @commands.has_any_role("Operations Command", "Command Consultant", "Campaign Host", "Operation Host")
    async def deleteOperation(self, ctx, operation_id=None):

        # Determine Op ID by channel name
        if operation_id == None:
            operation_id = str(ctx.channel)[0]
        else:
            operation_id = str(operation_id)

        # Find bot-commands channel
        botCommandsChannel = nextcord.utils.get(ctx.guild.channels, name=f"bot-commands")

        # Delete User Message before Update
        try:
            await ctx.message.delete()
        except:
            print()

        # Check if operation exists
        if self.database['operations'].get(operation_id) == None:
            return await botCommandsChannel.send(f"Operation ID {operation_id} not found.")

        # Check if roster_category exists, otherwise create it
        for category in ctx.guild.categories:
            if category.name == 'rosters':
                self.roster_category = category
                break
            
        # Delete operation channel
        if self.roster_category:
            channel = nextcord.utils.get(ctx.guild.channels, name=f"{operation_id}-{self.database['operations'][operation_id]['channel_name']}", category=self.roster_category)
            if channel:
                await channel.delete()
                await botCommandsChannel.send(f"{ctx.author.mention} has deleted {self.database['operations'][operation_id]['channel_name']}.")
        deletedunit = self.database['operations'][operation_id]['channel_name']
        # Remove operation channel in database
        del self.database['operations'][operation_id]
        self.saveData()

        # Notify user
        await botCommandsChannel.send(f"{ctx.author.mention} removed operation {deletedunit}.")

    # Dumps data to autoSlot.json
    def saveData(self):
        with open('autoSlot.json', 'w') as f:
            json.dump(self.database, f)

    #Convert to produce embed, with fields acting as group. Character limit is 1024, so limit groups to be 500.
    def embedGroupsToRoster(self,ctx, operation_id, group_dict):
        slots = ""
        assignments = self.database['operations'][operation_id]['assignments']
        long_operation_timestamp = "<t:" + str(self.database['operations'][operation_id]['operation_timestamp']) + ":F>" #nextcord.utils.format_dt(self.database['operations'][operation_id]['operation_timestamp'], style="F")
        relative_operation_timestamp = "<t:" + str(self.database['operations'][operation_id]['operation_timestamp']) + ":R>" #nextcord.utils.format_dt(self.database['operations'][operation_id]['operation_timestamp'], style="R")
        slot_embed = nextcord.Embed(title=f"{self.database['operations'][operation_id]['name']}", description=f"By: {ctx.guild.get_member(self.database['operations'][operation_id]['author']).mention}\n {long_operation_timestamp}, {relative_operation_timestamp}\n Operation ID: {operation_id}", color=0x0E8643)
        if len(group_dict) > 10:
            return None
        for group in group_dict:
            slots = ""
            slot_dict = self.database['operations'][operation_id]['groups'][group]
            if len(slot_dict) > 20:
                return None
            for slot in slot_dict:
                if len(slot) > 25:
                    return None
                if assignments.get(slot) == None:
                    slots = slots + (f"{slot}: {self.database['operations'][operation_id]['groups'][group][slot]}\n")
                else:
                    slots = slots + (f"{slot}: {self.database['operations'][operation_id]['groups'][group][slot]} - {ctx.guild.get_member(assignments.get(slot)).mention}\n")
            slot_embed.add_field(name=group, value=slots, inline=False)
        return slot_embed

    # Parse inputted slots into autoSlot format
    def parseStringToGroups(self,data):
        if ':' not in data:
            return False, False
        if data[-1] == ',':
            data = data.rstrip(data[-1])
            data = data + '.'
        elif data[-1] != '.':
            data = data + '.'
        data_list = data.split(" ")
        temp = ""
        group_list = []
        temp_list = []
        group_dict = {}
        for i in data_list:
            temp = temp + f'{i} '
            if ':' in i:
                temp = temp.rstrip(temp[-1])
                temp = temp.rstrip(temp[-1])
                group_list.append(temp)
                group_dict.update({temp : 'placeholder'})
                temp = ""
            if ',' in i:
                temp = temp.rstrip(temp[-1])
                temp = temp.rstrip(temp[-1])
                if temp != "":
                    temp_list.append(temp)
                    temp = ""
            if '.' in i:
                temp = temp.rstrip(temp[-1])
                temp = temp.rstrip(temp[-1])
                if temp != "":
                    temp_list.append(temp)
                    if len(group_list) > 0:
                        group_dict.update({group_list[len(group_list) - 1] : temp_list})
                    else:
                        group_dict.update({group_list[0] : temp_list})
                    temp = ""
                    temp_list = []
        group_alt = {}
        slots = {}
        slot_counter = 1
        for group in group_list:
            for slot in group_dict[group]:
                slots.update({str(slot_counter) : slot})
                slot_counter = slot_counter + 1
            group_alt.update({group : slots})
            slots = {}
        group_dict = group_alt
        return group_list, group_dict

    def updateDict(self, new_dict):
        for key, value in new_dict.items():
            if isinstance(value, collections.Mapping):
                default = value.copy()
                default.clear()
                r = self.updateDict(self.database.get(key, default), value)
                self.database[key] = r
            else:
                self.database[key] = value
        return self.database

def setup(client):
    client.add_cog(autoSlot(client))