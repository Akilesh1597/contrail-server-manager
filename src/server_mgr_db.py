#!/usr/bin/python

import sqlite3 as lite
import sys
import pdb
import uuid
from netaddr import *
from server_mgr_err import *
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger

def_server_db_file = 'smgr_data.db'
cluster_table = 'cluster_table'
server_table = 'server_table'
image_table = 'image_table'
inventory_table = 'inventory_table'
server_status_table = 'status_table'
server_tags_table = 'server_tags_table'
_DUMMY_STR = "DUMMY_STR"


class ServerMgrDb:

    _cluster_table_cols = []
    _server_table_cols = []
    _image_table_cols = []
    _status_table_cols = []
    _server_tags_table_cols = []
    _inventory_table_cols = []

    # Keep list of table columns
    def _get_table_columns(self):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.execute(
                    "SELECT * FROM " +
                    server_table + " WHERE id=?", (_DUMMY_STR,))
                self._server_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    server_tags_table + " WHERE tag_id=?", (_DUMMY_STR,))
                self._server_tags_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    image_table + " WHERE id=?", (_DUMMY_STR,))
                self._image_table_cols = [x[0] for x in cursor.description]
                cursor.execute("SELECT * FROM " +
                               cluster_table + " WHERE id=?", (_DUMMY_STR,))
                self._cluster_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    server_status_table + " WHERE id=?", (_DUMMY_STR,))
                self._status_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    inventory_table + " WHERE id=?", (_DUMMY_STR,))
                self._inventory_table_cols = [x[0] for x in cursor.description]
        except Exception as e:
            raise e
    # end _get_table_columns

    def _add_table_column(self, cursor, table, column, column_type):
        try:
            cmd = "ALTER TABLE " + table + " ADD COLUMN " + column + " " + column_type
            cursor.execute(cmd)
        except lite.OperationalError:
            pass
    # end _add_table_column

    def log_and_raise_exception(self, msg, err_code = ERR_OPR_ERROR):
         self._smgr_log.log(self._smgr_log.ERROR, msg)
         raise ServerMgrException(msg, err_code)

    def __init__(self, db_file_name=def_server_db_file):
        try:
            self._smgr_log = ServerMgrlogger()
            self._con = lite.connect(db_file_name)
            with self._con:
                cursor = self._con.cursor()
                # Create cluster table.
                cursor.execute("CREATE TABLE IF NOT EXISTS " + cluster_table +
                               """ (id TEXT PRIMARY KEY,
                                    parameters TEXT,
                                    email TEXT)""")
                # Create image table
                cursor.execute("CREATE TABLE IF NOT EXISTS " +
                               image_table + """ (id TEXT PRIMARY KEY,
                    version TEXT, type TEXT, path TEXT,
                    parameters TEXT)""")
                # Create status table
                cursor.execute("CREATE TABLE IF NOT EXISTS " +
                               server_status_table + """ (id TEXT PRIMARY KEY,
                            server_status TEXT)""")
                # Create server table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + server_table +
                    """ (mac_address TEXT PRIMARY KEY NOT NULL,
                         id TEXT, host_name TEXT, static_ip varchar default 'N',
                         ip_address TEXT, subnet_mask TEXT, gateway TEXT, domain TEXT,
                         cluster_id TEXT,  base_image_id TEXT,
                         package_image_id TEXT, password TEXT,
                         last_update TEXT, discovered varchar default 'false',
                         parameters TEXT, roles TEXT, ipmi_username TEXT,
                         ipmi_password TEXT, ipmi_address TEXT,
                         ipmi_type TEXT, intf_control TEXT,
                         intf_data TEXT, intf_bond TEXT,
                         email TEXT, status TEXT,
                         tag1 TEXT, tag2 TEXT, tag3 TEXT,
                         tag4 TEXT, tag5 TEXT, tag6 TAXT, tag7 TEXT,
                         network TEXT, contrail TEXT, top_of_rack TEXT,
                         UNIQUE (id))""")
                # Create inventory table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + inventory_table +
                    """ (fru_description TEXT PRIMARY KEY NOT NULL,
                         id TEXT, board_serial_number TEXT, chassis_type TEXT,
                         chassis_serial_number TEXT, board_mfg_date TEXT,
                         board_manufacturer TEXT, board_product_name TEXT,
                         board_part_number TEXT, product_manfacturer TEXT,
                         product_name TEXT, product_part_number TEXT,
                         UNIQUE (fru_description))""")
                # Create server tags table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + server_tags_table +
                    """ (tag_id TEXT PRIMARY KEY NOT NULL,
                         value TEXT,
                         UNIQUE (tag_id),
                         UNIQUE (value))""")
                # Add columns for image_table
                self._add_table_column(cursor, image_table, "category", "TEXT")
                # Add columns for cluster_table
                self._add_table_column(cursor, cluster_table, "base_image_id", "TEXT")
                self._add_table_column(cursor, cluster_table, "package_image_id", "TEXT")
                self._add_table_column(cursor, cluster_table, "provisioned_id", "TEXT")
                self._add_table_column(cursor, cluster_table, "provision_role_sequence", "TEXT")
                # Add columns for server_table
                self._add_table_column(cursor, server_table, "reimaged_id", "TEXT")
                self._add_table_column(cursor, server_table, "provisioned_id", "TEXT")
                self._add_table_column(cursor, server_table, "network", "TEXT")
                self._add_table_column(cursor, server_table, "top_of_rack", "TEXT")
                self._add_table_column(cursor, server_table, "contrail", "TEXT")
                self._add_table_column(cursor, server_table, "ssh_public_key", "TEXT")
                self._add_table_column(cursor, server_table, "ssh_private_key", "TEXT")

            self._get_table_columns()
            self._smgr_log.log(self._smgr_log.DEBUG, "Created tables")

            # During init, we check if any of the Cluster in DB are missing any Storage Parameters (Generated UUIDs)
            cluster_list = self._get_items(cluster_table, None,
                                       None, True, None)
            for cluster in cluster_list:
                # Check if storage parameters are present in Cluster, else generate them
                if 'storage_fsid' not in set(eval(cluster['parameters'])) or 'storage_virsh_uuid' not in set(eval(
                        cluster['parameters'])):
                    self.update_cluster_uuids(cluster)
            self.convert_server_table_to_new_interface()
        except e:
            raise e
    # End of __init__

    def get_subnet_mask(self, server):
        subnet_mask = server.get('subnet_mask', None)
        if not subnet_mask:
            cluster = server.get('cluster', None)
            if cluster:
                subnet_mask = cluster.get('subnet_mask', None)
        return subnet_mask
    # End get_subnet_mask

    def get_server_domain(self, server_id):
        server_domain = ""
        if not server_id:
            return server_domain
        servers = self.get_server(
            {"id" : server_id}, detail=True)
        if not servers:
            msg = "No server found with server_id " + server_id
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return server_domain
        server = servers[0]
        server_domain = server.get('domain', "")
        if not server_domain:
            cluster_id = server.get('cluster_id', "")
            if not cluster_id:
                msg = "No domain found for server_id " + server_id
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                return server_domain
            clusters = self.get_cluster(
                {"id" : cluster_id}, detail=True)
            if not clusters:
                msg = "No domain found for server_id %s, no cluster for cluster_id %s," \
                    % (server_id, cluster_id)
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                return server_domain
            cluster = clusters[0]
            cluster_params = eval(cluster['parameters'])
            server_domain = cluster_params.get('domain', "")
            if not server_domain:
                msg = "No domain found for server_id %s, cluster_id %s" \
                    % (server_id, cluster_id)
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                return server_domain
        return server_domain
    # End get_server_domain

    def convert_server_config_to_new_interface(self, server):
        if not server:
            return
        # Check for network and contrail blocks and skip conversion
        contrail = server.get('contrail', "")
        if contrail:
            contrail = eval(contrail)
        network = server.get('network', "")
        if network:
            network = eval(network)
        if network and contrail:
            return
        update_server = {}
        network = {}
        contrail = {}
        interfaces = []
        # Management interface
        server_parameters = server.get('parameters', "{}")
        if not server_parameters:
            server_parameters = "{}"
        server_parameters = eval(server_parameters)
        interface_name = server_parameters.get('interface_name', "")
        if interface_name:
            # Management interface, convert to new way
            network['management_interface'] = interface_name
            interface = {}
            interface['name'] = interface_name
            interface['dhcp'] = True
            ip_address = server.get('ip_address', "")
            subnet_mask = self.get_subnet_mask(server)
            if ip_address:
                ip_str = ip_address
                if subnet_mask:
                    ip_str = ip_str + '/' + subnet_mask
                ip = IPNetwork(ip_str)
                interface['ip_address'] = str(ip)
            mac_address = server.get('mac_address', "")
            if mac_address:
                interface['mac_address'] = mac_address
            gateway = server.get('gateway', "")
            if gateway:
                interface['default_gateway'] = gateway
            interfaces.append(interface)

        #Control/data interface
        intf_control = server.get('intf_control', None)
        intf_bond = server.get('intf_bond', None)
        if intf_control:
            intf_control = eval(intf_control)
            for key in intf_control.keys():
                interface = {}
                control_interface = intf_control[key]
                ip_address = control_interface.get('ip_address', None)
                interface['name'] = key
                if ip_address:
                    interface['ip_address'] = ip_address
                if intf_bond:
                    intf_bond = eval(intf_bond)
                    for bond_key in intf_bond.keys():
                        bond_interface = intf_bond.get(bond_key, None)
                        if bond_interface:
                            interface['type'] = 'bond0'
                            options = bond_interface.get('bond_options', None)
                            if options:
                                interface['bond_options'] = options
                            members = bond_interface.get('member_interfaces', None)
                            if members:
                                interface['members'] = members
                            if key == bond_key:
                                contrail['contrail_data_interface'] = key
                            break
                interfaces.append(interface)
                break
        if interfaces:
            network['interfaces'] = interfaces
            network['provisioning'] = 'kickstart'
        update_server['contrail'] = contrail
        update_server['network'] = network
        update_server['mac_address'] = server['mac_address']
        self.modify_server(update_server)
    # End convert_server_config_to_new_interface

    def modify_server_to_new_interface_config(self, server_data):
        if not server_data:
            return
        mac_address = server_data.get('mac_address', None)
        id = server_data.get('id', None)
        servers = []
        if mac_address:
            servers = self.get_server(
                {'mac_address' : mac_address}, detail=True)
        elif id:
            servers = self.get_server(
                {'id': id}, detail=True)
        if not servers:
            return
        self.convert_server_config_to_new_interface(servers[0])

    def convert_server_table_to_new_interface(self):
        servers = self.get_server(None, detail=True)
        for server in servers:
            self.convert_server_config_to_new_interface(server)
    # End convert_server_table_to_new_interface

    def delete_tables(self):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.executescript("""
                DELETE FROM """ + cluster_table + """;
                DELETE FROM """ + server_table + """;
                DELETE FROM """ + server_tags_table + """;
                DELETE FROM """ + server_status_table + """;
                DELETE FROM """ + inventory_table + """;
                DELETE FROM """ + image_table + ";")
        except:
            raise e
    # End of delete_tables

    def get_server_id(self, server_mac):
        try:
            if server_mac:
                server_mac = str(EUI(server_mac)).replace("-", ":")
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT id FROM " +
                               server_table + " WHERE mac_address=?",
                              (server_mac,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return None
        except:
            return None
    # end get_server_id

    # Below function returns value corresponding to tag_id from
    # server_tags_table
    def get_server_tag(self, tag_id):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT value FROM " +
                               server_tags_table + " WHERE tag_id=?",
                              (tag_id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return None
        except:
            return None
    # end get_server_tag

    def get_server_mac(self, id):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT mac_address FROM " +
                               server_table + " WHERE id=?",
                              (id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return None
        except:
            return None

    def _add_row(self, table_name, dict):
        try:
            keys, values = zip(*dict.items())
            insert_str = "INSERT OR IGNORE INTO %s (%s) values (%s)" \
                % (table_name,
                   (",".join(keys)),
                   (",".join('?' * len(keys))))
            with self._con:
                cursor = self._con.cursor()
                cursor.execute(insert_str, values)
        except Exception as e:
            raise e
    # end _add_row

    # Generic function to delete rows matching given criteria
    # from given table.
    # Match dict is dictionary of columns and values to match for.
    # unmatch dict is not of dictionaty of columns and values to match for.
    def _delete_row(self, table_name,
                    match_dict=None, unmatch_dict=None):
        try:
            delete_str = "DELETE FROM %s" %(table_name)
            # form a string to provide to where match clause
            match_list = []
            where = None
            if match_dict:
                where = match_dict.get("where", None)

            if where:
                delete_str += " WHERE " + where
            else:
                if match_dict:
                    match_list = ["%s = \'%s\'" %(
                            k,v) for k,v in match_dict.iteritems()]
                if unmatch_dict:
                    match_list += ["%s != \'%s\'" %(
                            k,v) for k,v in unmatch_dict.iteritems()]
                if match_list:
                    match_str = " and ".join(match_list)
                    delete_str+= " WHERE " + match_str

            with self._con:
                cursor = self._con.cursor()
                cursor.execute(delete_str)
        except Exception as e:
            raise e
    # End _delete_row

    def _modify_row(self, table_name, dict,
                    match_dict=None, unmatch_dict=None):
        try:
            keys, values = zip(*dict.items())
            modify_str = "UPDATE %s SET " % (table_name)
            update_list = ",".join(key + "=?" for key in keys)
            modify_str += update_list
            match_list = []
            if match_dict:
                match_list = ["%s = ?" %(
                    k) for k in match_dict.iterkeys()]
                match_values = [v for v in match_dict.itervalues()]
            if unmatch_dict:
                match_list += ["%s != ?" %(
                    k) for k in unmatch_dict.iterkeys()]
                match_values += [v for v in unmatch_dict.itervalues()]
            if match_list:
                match_str = " and ".join(match_list)
                match_values_str = ",".join(match_values)
                modify_str += " WHERE " + match_str
                values += (match_values_str,)
            with self._con:
                cursor = self._con.cursor()
                cursor.execute(modify_str, values)
        except Exception as e:
            raise e

    def _get_items(
        self, table_name, match_dict=None,
        unmatch_dict=None, detail=False, always_fields=None):
        try:
            with self._con:
                cursor = self._con.cursor()
                if detail:
                    sel_cols = "*"
                else:
                    sel_cols = ",".join(always_fields)
                select_str = "SELECT %s FROM %s" % (sel_cols, table_name)
                # form a string to provide to where match clause
                match_list = []
                where = None
                if match_dict:
                    where = match_dict.get("where", None)
                if where:
                    select_str += " WHERE " + where
                else:
                    if match_dict:
                        match_list = ["%s = \'%s\'" %(
                                k,v) for k,v in match_dict.iteritems()]
                    if unmatch_dict:
                        match_list += ["%s != \'%s\'" %(
                                k,v) for k,v in unmatch_dict.iteritems()]
                    if match_list:
                        match_str = " and ".join(match_list)
                        select_str+= " WHERE " + match_str
                cursor.execute(select_str)
            rows = [x for x in cursor]
            cols = [x[0] for x in cursor.description]
            items = []
            for row in rows:
                item = {}
                for prop, val in zip(cols, row):
                    item[prop] = val
                items.append(item)
            return items
        except Exception as e:
            raise e
    # End _get_items

    def add_cluster(self, cluster_data):
        try:
            # Store cluster_parameters dictionary as a text field
            cluster_parameters = cluster_data.pop("parameters", None)
            if cluster_parameters is not None:
                cluster_data['parameters'] = str(cluster_parameters)
            # Store provision sequence list as a text field
            provision_role_sequence = cluster_data.pop("provision_role_sequence",
                                                       None)
            if provision_role_sequence is not None:
                cluster_data['provision_role_sequence'] = str(provision_role_sequence)
            # Store email list as text field
            email = cluster_data.pop("email", None)
            if email is not None:
                cluster_data['email'] = str(email)
            self._add_row(cluster_table, cluster_data)
        except Exception as e:
            raise e
    # End of add_cluster

    def add_inventory(self, fru_data):
        try:
            fru_data = dict(fru_data)
            if fru_data and 'id' in fru_data:
                self._add_row(inventory_table, fru_data)
                self._smgr_log.log(self._smgr_log.DEBUG, "ADDED FRU INFO FOR " + fru_data['id'])
        except Exception as e:
            return e.message
        return 0
    # End of add_inventory

    def add_server(self, server_data):
        try:
            if 'mac_address' in server_data:
                server_data['mac_address'] = str(
                    EUI(server_data['mac_address'])).replace("-", ":")
            # Store roles list as a text field
            roles = server_data.pop("roles", None)
            cluster_id = server_data.get('cluster_id', None)
            if cluster_id:
                self.check_obj(
                    "cluster", {"id" : cluster_id})
            if roles is not None:
                server_data['roles'] = str(roles)
            intf_control = server_data.pop("control_data_network", None)
            if intf_control:
                server_data['intf_control'] = str(intf_control)
            intf_bond = server_data.pop("bond_interface", None)
            if intf_bond:
                server_data['intf_bond'] = str(intf_bond)
            #Add network
            if 'network' in server_data:
                network_data_str = str(server_data.pop("network", None))
                server_data['network'] = network_data_str
            #Add top_of_rack configuration 
            if 'top_of_rack' in server_data:
                top_of_rack_data_str = str(server_data.pop("top_of_rack", None))
                server_data['top_of_rack'] = top_of_rack_data_str 
            #Add contrail
            if 'contrail' in server_data:
                contrail_data_str = str(server_data.pop("contrail", None))
                server_data['contrail'] = contrail_data_str

            # Store email list as text field
            email = server_data.pop("email", None)
            if email:
                server_data['email'] = str(email)
            # store tags if any
            server_tags = server_data.pop("tag", None)
            if server_tags is not None:
                tags_dict = self.get_server_tags(detail=True)
                rev_tags_dict = dict((v,k) for k,v in tags_dict.iteritems())
                for k,v in server_tags.iteritems():
                    server_data[rev_tags_dict[k]] = v
            # Store server_params dictionary as a text field
            server_parameters = server_data.pop("parameters", None)
            if server_parameters is not None:
                server_data['parameters'] = str(server_parameters)
            self._add_row(server_table, server_data)
        except Exception as e:
            raise e
        return 0
    # End of add_server

    # This function for adding server tag is slightly different
    # compared with add function for other tables. The tag_data
    # contains tag information for all tags.
    # This function is always called with complete list of tags
    # so, clear the table first.
    def add_server_tags(self, tag_data):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.executescript("""
                DELETE FROM """ + server_tags_table + ";")
            for key,value in tag_data.iteritems():
                row_data = {
                    'tag_id' : key,
                    'value' : value }
                self._add_row(server_tags_table, row_data)
        except Exception as e:
            raise e
    # End of add_server_tags

    def server_discovery(self, action, entity):
        try:
            if 'mac_address' in entity:
                entity['mac_address'] = str(EUI(entity['mac_address'])).replace("-", ":")
            mac_address = entity.get("mac_address", None)
            if action.lower() == "add":
                # If this server is already present in our table,
                # update IP address if DHCP was not static.
                servers = self._get_items(
                    server_table, {"mac_address" : mac_address},detail=True)
                if servers:
                    server = servers[0]
                    self._modify_row(
                        server_table, entity,
                        {"mac_address": mac_address}, {})
                    return
                # Adding network and contrail blocks
                entity['parameters'] = "{}"
                entity['network'] = "{}"
                entity['contrail'] = "{}"
                entity['discovered'] = "true"
                entity['status'] = "server_discovered"
                self._add_row(server_table, entity)
            elif action.lower() == "delete":
                servers = self.get_server({"mac_address" : mac_address}, detail=True)
                if ((servers) and (servers[0]['discovered'] == "true")):
                    self._delete_row(server_table,
                                     {"mac_address" : mac_address})
            else:
                return
        except Exception as e:
            return
    # End of server_discovery

    def add_image(self, image_data):
        try:
            # Store image_parameters dictionary as a text field
            image_parameters = image_data.pop("parameters", None)
            if image_parameters is not None:
                image_data['parameters'] = str(image_parameters)
            self._add_row(image_table, image_data)
        except Exception as e:
            raise e
    # End of add_image

    def delete_cluster(self, match_dict=None, unmatch_dict=None):
        try:
            self.check_obj("cluster", match_dict, unmatch_dict)
            cluster_id = match_dict.get("id", None)
            servers = None
            if cluster_id:
                servers = self.get_server({'cluster_id' : cluster_id}, detail=True)
            if servers:
                msg = ("Servers are present in this cluster, "
                        "remove cluster association, prior to cluster delete.")
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            self._delete_row(cluster_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_cluster

    def check_obj(self, type,
                  match_dict=None, unmatch_dict=None, raise_exception=True):
        if type == "server":
            cb = self.get_server
            db_obj = cb(match_dict, unmatch_dict, detail=False)
        elif type == "cluster":
            cb = self.get_cluster
            db_obj = cb(match_dict, unmatch_dict, detail=False)
        elif type == "image":
            cb = self.get_image
            db_obj = cb(match_dict, unmatch_dict, detail=False)

        if not db_obj:
            msg = "%s not found" % (type)
            if raise_exception:
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            return False
        return True
    #end of check_obj

    def delete_server(self, match_dict=None, unmatch_dict=None):
        try:
            if match_dict and match_dict.get("mac_address", None):
                if match_dict["mac_address"]:
                    match_dict["mac_address"] = str(
                        EUI(match_dict["mac_address"])).replace("-", ":")
            if unmatch_dict and unmatch_dict.get("mac_address", None):
                if unmatch_dict["mac_address"]:
                    unmatch_dict["mac_address"] = str(
                        EUI(unmatch_dict["mac_address"])).replace("-", ":")
            self.check_obj("server", match_dict, unmatch_dict)
            self._delete_row(server_table,
                             match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_server

    def delete_server_tag(self, match_dict=None, unmatch_dict=None):
        try:
            self._delete_row(server_tags_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_server_tag

    def delete_image(self, match_dict=None, unmatch_dict=None):
        try:
            self.check_obj("image", match_dict, unmatch_dict)
            self._delete_row(image_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_image

    def modify_cluster(self, cluster_data):
        try:
            cluster_id = cluster_data.get('id', None)
            if not cluster_id:
                raise Exception("No cluster id specified")
            self.check_obj("cluster", {"id" : cluster_id})
            db_cluster = self.get_cluster(
                {"id" : cluster_id}, detail=True)
            if not db_cluster:
                msg = "%s is not valid" % cluster_id
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)

            db_cluster_params_str = db_cluster[0] ['parameters']
            db_cluster_params = {}
            if db_cluster_params_str:
                db_cluster_params = eval(db_cluster_params_str)
            if 'uuid' not in db_cluster_params:
                str_uuid = str(uuid.uuid4())
                cluster_data["parameters"].update({"uuid":str_uuid})
            # Store cluster_params dictionary as a text field
            cluster_params = cluster_data.pop("parameters", {})
            for k,v in cluster_params.iteritems():
                if v == '""':
                    v = ''
                db_cluster_params[k] = v
            cluster_params = db_cluster_params
            if cluster_params is not None:
                cluster_data['parameters'] = str(cluster_params)

            # Store email list as text field
            email = cluster_data.pop("email", None)
            if email is not None:
                cluster_data['email'] = str(email)
            
            provision_role_sequence = cluster_data.pop("provision_role_sequence",
                                                       None)
            if provision_role_sequence is not None:
                cluster_data['provision_role_sequence'] = str(provision_role_sequence)
            self._modify_row(
                cluster_table, cluster_data,
                {'id' : cluster_id}, {})
        except Exception as e:
            raise e
    # End of modify_cluster

    def modify_image(self, image_data):
        try:
            image_id = image_data.get('id', None)
            if not image_id:
                raise Exception("No image id specified")
            #Reject if non mutable field changes
            db_image = self.get_image(
                {'id' : image_data['id']},
                detail=True)
            if image_data['path'] != db_image[0]['path']:
                msg = ('Image path cannnot be modified')
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            if image_data['type'] != db_image[0]['type']:
                msg = ('Image type cannnot be modified')
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            # Store image_params dictionary as a text field
            image_parameters = image_data.pop("parameters", None)
            if image_parameters is not None:
                image_data['parameters'] = str(image_parameters)
            self._modify_row(
                image_table, image_data,
                {'id' : image_id}, {})
        except Exception as e:
            raise e
    # End of modify_image

    def modify_server(self, server_data):
        db_server = None
        if 'mac_address' in server_data.keys() and \
                 server_data['mac_address'] != None:
            db_server = self.get_server(
                {'mac_address' : server_data['mac_address']},
                detail=True)
        elif 'id' in server_data.keys() and server_data['id'] != None:
            db_server = self.get_server(
                {'id': server_data['id']},
                detail=True)
        if not db_server:
            return db_server
        try:
            cluster_id = server_data.get('cluster_id', None)
            if cluster_id:
                self.check_obj("cluster", {"id" : cluster_id})

            if 'mac_address' in server_data:
                server_data['mac_address'] = str(
                    EUI(server_data['mac_address'])).replace("-", ":")
            server_mac = server_data.get('mac_address', None)
            if not server_mac:
                server_id = server_data.get('id', None)
                if not server_id:
                    msg = ("No server MAC or id specified")
                    self.log_and_raise_exception(msg, ERR_OPR_ERROR)
                else:
                    server_mac = self.get_server_mac(server_id)
            #Check if object exists
            if 'id' in server_data.keys() and \
                    'server_mac' in server_data.keys():
                self.check_obj('server',
                               {'id' : server_data['id']})
                #Reject if primary key values change
                if server_data['mac_address'] != db_server[0]['mac_address']:
                    msg = ('MAC address cannnot be modified', ERR_OPR_ERROR)
                    self.log_and_raise_exception(msg, ERR_OPR_ERROR)


            # Store roles list as a text field
            roles = server_data.pop("roles", None)
            if roles is not None:
                server_data['roles'] = str(roles)
            intf_control = server_data.pop("control_data_network", None)
            if intf_control:
                server_data['intf_control'] = str(intf_control)
            intf_bond = server_data.pop("bond_interface", None)
            if intf_bond:
                server_data['intf_bond'] = str(intf_bond)

            #Add network
            if 'network' in server_data:
                network_data_str = str(server_data.pop("network", None))
                server_data['network'] = network_data_str
            #Add contrail
            if 'contrail' in server_data:
                contrail_data_str = str(server_data.pop("contrail", None))
                server_data['contrail'] = contrail_data_str

            # store tags if any
            server_tags = server_data.pop("tag", None)
            if server_tags is not None:
                tags_dict = self.get_server_tags(detail=True)
                rev_tags_dict = dict((v,k) for k,v in tags_dict.iteritems())
                for k,v in server_tags.iteritems():
                    server_data[rev_tags_dict[k]] = v

            if "ssh_private_key" and "ssh_public_key" in server_data:
                private_key = str(server_data.pop("ssh_private_key", None))
                public_key = str(server_data.pop("ssh_public_key", None))
                server_data["ssh_private_key"] = private_key
                server_data["ssh_public_key"] = public_key
            # Store server_params dictionary as a text field
            server_params = server_data.pop("parameters", None)
            #if server_params is not None:
            #    server_data['server_params'] = str(server_params)
            #check for modify in db server_params
            #Always Update DB server parmas
            db_server_params = {}
            if len(db_server) == 0:
                msg = ('DB server not found', ERR_OPR_ERROR)
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
               
            db_server_params_str = db_server[0] ['parameters']
            if db_server_params_str:
                db_server_params = eval(db_server_params_str)
                if server_params:
                    for k,v in server_params.iteritems():
                        if v == '""':
                            v = ''
                        db_server_params[k] = v
            server_data['parameters'] = str(db_server_params)

            # Store email list as text field                   
            email = server_data.pop("email", None)
            if email is not None:
                server_data['email'] = str(email)
            self._modify_row(
                server_table, server_data,
                {'mac_address' : server_mac}, {})
            return db_server
        except Exception as e:
            raise e
    # End of modify_server

    # This function for modifying server tag is slightly different
    # compared with modify function for other tables. The tag_data
    # contains tag information for all tags.
    def modify_server_tags(self, tag_data):
        try:
            for key,value in tag_data.iteritems():
                row_data = {
                    'tag_id' : key,
                    'value' : value }
                self._modify_row(
                    server_tags_table, row_data,
                    {'tag_id' : key}, {})
        except Exception as e:
            raise e
    # End of modify_server_tags

    def get_image(self, match_dict=None, unmatch_dict=None,
                  detail=False, field_list=None):
        try:
            if not field_list:
                field_list = ["id"]
            images = self._get_items(
                image_table, match_dict,
                unmatch_dict, detail, field_list)
        except Exception as e:
            raise e
        return images
    # End of get_image

    def get_server_tags(self, match_dict=None, unmatch_dict=None,
                  detail=True):
        try:
            tag_dict = {}
            tags = self._get_items(
                server_tags_table, match_dict,
                unmatch_dict, True, ["tag_id"])
            for tag in tags:
                tag_dict[tag['tag_id']] = tag['value']
        except Exception as e:
            raise e
        return tag_dict
    # End of get_server_tags

    def get_status(self, match_key=None, match_value=None,
                  detail=False):
        try:
            status = self._get_items(
                server_status_table, {match_key : match_value},
                detail=detail, always_field=["id"])
        except Exception as e:
            raise e
        return status
    # End of get_status

    def put_status(self, server_data):
        try:
            server_id = server_data.get('id', None)
            if not server_id:
                raise Exception("No server id specified")
            # Store vns_params dictionary as a text field
            servers = self._get_items(
                server_status_table, {"id" : server_id},detail=True)
            if servers:
                self._modify_row(
                    server_status_table, server_data,
                    {'id' : server_id}, {})
            else:
                self._add_row(server_status_table, server_data)
        except Exception as e:
            raise e
    # End of put_status


    def get_server(self, match_dict=None, unmatch_dict=None,
                   detail=False, field_list=None):
        try:
            if match_dict and match_dict.get("mac_address", None):
                if match_dict["mac_address"]:
                    match_dict["mac_address"] = str(
                        EUI(match_dict["mac_address"])).replace("-", ":")
            # For server table, when detail is false, return server_id, mac
            # and ip.
            if not field_list:
                field_list = ["id", "mac_address", "ip_address"]
            servers = self._get_items(
                server_table, match_dict,
                unmatch_dict, detail, field_list)
        except Exception as e:
            raise e
        return servers
    # End of get_server

    def get_inventory(self, match_dict=None, unmatch_dict=None):
        try:
            frus = self._get_items(inventory_table, match_dict, unmatch_dict, True, None)
        except Exception as e:
            raise e
        return frus
    # End of get_inventory

    def get_cluster(self, match_dict=None,
                unmatch_dict=None, detail=False, field_list=None):
        try:
            if not field_list:
                field_list = ["id"]
            cluster = self._get_items(
                cluster_table, match_dict,
                unmatch_dict, detail, field_list)
        except Exception as e:
            raise e
        return cluster
    # End of get_cluster

    # If any UUIDs are missing from an existing Cluster, we add them during ServerManager DB init
    def update_cluster_uuids(self, cluster):
        try:
            db_cluster_params_str = cluster['parameters']
            db_cluster_params = {}
            if db_cluster_params_str:
                db_cluster_params = eval(db_cluster_params_str)
            if 'uuid' not in db_cluster_params:
                str_uuid = str(uuid.uuid4())
                db_cluster_params.update({"uuid": str_uuid})
            if 'storage_fsid' not in db_cluster_params:
                storage_fsid = str(uuid.uuid4())
                db_cluster_params.update({"storage_fsid": storage_fsid})
            if 'storage_virsh_uuid' not in db_cluster_params:
                storage_virsh_uuid = str(uuid.uuid4())
                db_cluster_params.update({"storage_virsh_uuid": storage_virsh_uuid})
        except Exception as e:
            raise e

        cluster['parameters'] = str(db_cluster_params)
        self._modify_row(
            cluster_table, cluster,
            {'id' : cluster['id']}, {})
    # End of update_cluster_uuids

# End class ServerMgrDb

if __name__ == "__main__":
    pass

