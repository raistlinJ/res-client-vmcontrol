from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import logging
import time
import Pyro5.api

import os

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Route to serve the HTML page (client)
@app.route('/')
@limiter.limit("1/second", override_defaults=False)
def index():
    return render_template('index.html')

# Route to run a command
@app.route('/run_command', methods=['POST', 'OPTIONS'])
@limiter.limit("1 per 30 minutes")
def run_command():
    # Get the password and configname from the request
    data = request.json
    username = data.get('username')
    password = data.get('password')
    configname = data.get('configname')
    command = data.get('command')
    
    # Check if configname is provided
    if not configname:
        return jsonify({"error": "No Scenario Name Provided"}), 400

    try:
        # Call the start vm command
        
        ns = Pyro5.api.locate_ns(ip,port)
        
        pEngine = Pyro5.api.Proxy(ns.lookup("engine"))
        pUserPool = Pyro5.api.Proxy(ns.lookup("userpool"))
        
        res = pEngine.execute("vm-manage mgrstatus")
        while res["writeStatus"] != 0:
            time.sleep(.1)
            logging.debug("Waiting for experiment start to complete...")
            res = pEngine.execute("vm-manage mgrstatus")

        creds_file = ""
        usersConns = pUserPool.generateUsersConns(configname, creds_file=creds_file)
        if (username, password) in usersConns:
            conn = usersConns[(username, password)][0]
            cloneVMName = conn[0]
        else:
            return jsonify({"error": "Invalid username or password"}), 403
        
        #####---Start Experiment Test#####
        ##Note that any guestcontrol operations will require guest additions to be installed on the VM
        logging.info("Starting Experiment")

        cmds = []
        if command == "start":
            cmds.append("experiment start " + configname + " vm " + str(cloneVMName))
            for cmd in cmds:
                pEngine.execute(cmd)
                res = pEngine.execute("experiment status")
                logging.debug("Waiting for experiment start to complete...")

                while res["writeStatus"] != 0:
                    time.sleep(.1)
                    logging.debug("Waiting for experiment start to complete...")
                    res = pEngine.execute("experiment status")
            output = "Completed"
            #output += "\n" + str(res)

        elif command == "stop":
            cmds.append("experiment stop " + configname + " vm " + str(cloneVMName))
            for cmd in cmds:
                pEngine.execute(cmd)
                res = pEngine.execute("vm-manage mgrstatus")
                logging.debug("Waiting for experiment stop to complete...")
                while res["writeStatus"] != 0:
                    time.sleep(.1)
                    logging.debug("Waiting for experiment stop to complete...")
                    res = pEngine.execute("experiment status")
            output = "Completed"
            #output += "\n" + str(res)

        elif command == "status":
            cmd = "vm-manage refresh " + str(cloneVMName)
            pEngine.execute(cmd)
            res = pEngine.execute("vm-manage mgrstatus")
            logging.debug("Waiting for vm refresh update to complete...")
            while res["writeStatus"] != 0:
                time.sleep(.1)
                logging.debug("Waiting for vm refresh update to complete...")
                res = pEngine.execute("vm-manage mgrstatus")
            res = pEngine.execute("vm-manage vmstatus " + str(cloneVMName))
            if res != None and "vmState" in res and res["vmState"] != None and res["vmState"] != "" and "vmName" in res and res["vmName"] != None and res["vmName"] != "":
                vmName = os.path.basename(res["vmName"])
                output = "VM: " + str(vmName) + "\nStatus: " + str(res["vmState"])
            else:
                output = "Error Querying VM State"
            #output += "\n" + str(res)
                    
        elif command == "restore":
            cmds.append("experiment restore " + configname + " vm " + str(cloneVMName))
            for cmd in cmds:
                pEngine.execute(cmd)
                res = pEngine.execute("experiment status")
                logging.debug("Waiting for experiment restore to complete...")
                while res["writeStatus"] != 0:
                    time.sleep(.1)
                    logging.debug("Waiting for experiment restore to complete...")
                    res = pEngine.execute("experiment status")
            output = "Completed\n"
            #output += "\n" + str(res)
        
        return jsonify({"output": output}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500