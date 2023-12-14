"""
python 3.10.7
working Feb. 17 2023
a script to delete all possible messages from your data package using the Discord API
to use: paste your auth token and run script from package/messages
also, it's going to take a while due to rate limiting
"""

import os
import http.client as hc
import time
import json

#time between requests in seconds, experimentally this seemed to be right below the rate limit long-term
#TODO implement multiple connections?
delay = 1.75
lsdir = filter(lambda x: os.path.isdir(x), os.listdir())
#info about parsing messages.csv:
#the first row is a header
#multiple attachments to a single message are separated by spaces
#quotes that occur in a message are escaped with another quote
#multiline messages (containing newlines) and messages containing commas or quotes are enclosed in quotes
#we only care about extracting the id, so preprocess by removing all doubled (escaped) quote occurences and then remove everything enclosed by quotes
preprocess = lambda file: "".join(file.read().replace("\"\"", "").split("\"")[::2]).splitlines()[1:]
to_delete = {dir[1:]: [line[:line.index(",")] for line in preprocess(open(dir + "/messages.csv", encoding = "utf8"))] for dir in lsdir}
total = sum(len(to_delete[channel]) for channel in to_delete.keys())

print(f"found {total} messages, eta {int(total*delay/3600)} hours at {delay} seconds per message")
print("enter start index (inclusive, 1-based):")
print("(if the connection was interrupted, enter the index of the last message)")
progress = input("(to delete all, enter 1)\n")
while not (progress.isnumeric() and int(progress) <= total):
    input("enter start index (inclusive, 1-based):\n")
progress = int(progress)
runtot = 0
for channel in to_delete.copy().keys():
    runtot += len(to_delete[channel])
    if runtot < progress:
        to_delete.pop(channel)
    else:
        to_delete[channel] = to_delete[channel][progress - (runtot - len(to_delete[channel])) - 1:]
        break

conf = input("enter yes to confirm delete:\n")
while conf != "yes":
    conf = input("enter yes to confirm delete:\n")

fails = 0
runtot = 0
con = hc.HTTPSConnection("discord.com")
for channel in to_delete.keys():
    for msg in to_delete[channel]:
        send_more_requests = True
        skip_channel = False
        while send_more_requests:
            #paste your auth token here
            con.request("DELETE", f"/api/v9/channels/{channel}/messages/{msg}", headers = {"Authorization": ""})
            re = con.getresponse()
            body = re.read().decode("utf-8")
            print(f"message {progress}/{total} ({int(progress/total*100)}%): {re.status}", end = " ")
            match re.status:
                case 204:
                    #message was deleted successfully
                    print("No Content")
                    progress += 1
                    send_more_requests = False
                case 401:
                    #missing auth token
                    print("Unauthorized")
                    print("(did you paste your auth token?)")
                    input("\n")
                    exit()
                case 404:
                    #message has already been deleted
                    print("Not Found")
                    progress += 1
                    send_more_requests = False
                case 403:
                    #missing access to the remaining messages in this channel
                    if json.loads(body)["code"] == 5001:
                        print("Forbidden (missing access)")
                        print(f"(skipping the rest of channel {channel})")
                        progress += len(to_delete[channel]) - (progress - runtot)
                        fails += len(to_delete[channel]) - (progress - runtot)
                        skip_channel = True
                        break
                    #undeletable system message
                    print("Forbidden (undeletable system message)")
                    progress += 1
                    send_more_requests = False
                case 429:
                    #rate limited
                    print("Too Many Requests")
                    time.sleep(int(re.getheader("retry-after")))
                case other:
                    #idk
                    print(re.getheaders())
                    choice = input("unexpected response, see headers above, enter retry or skip:\n")
                    while choice != "retry" and choice != "skip":
                        choice = input("enter retry or skip:\n")
                    if choice == "skip":
                        progress += 1
                        send_more_requests = False
        time.sleep(delay)
        if skip_channel:
            break
    runtot += len(to_delete[channel])
con.close()

print(f"done, {fails} ({int(fails/total*100)}%) messages could not be deleted due to missing access")
input("\n")
