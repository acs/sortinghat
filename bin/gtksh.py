#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Alvaro del Castillo <acs@bitergia.com>

import argparse
import logging

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from sortinghat import api
from sortinghat.db.database import Database

def get_params():
    ''' Get params definition from ElasticOcean and from all the backends '''

    parser = argparse.ArgumentParser()


    parser.add_argument('-g', '--debug', dest='debug',
                        action='store_true',
                        help='Show debugging log')
    parser.add_argument('--db-user', help="User for db connection (default to root)",
                        default="root")
    parser.add_argument('--db-password', help="Password for db connection (default empty)",
                        default="")
    parser.add_argument('--db-host', help="Host for db connection (default to mariadb)",
                        default="")
    parser.add_argument('--db-sh', help="SortingHat DB (default to sh)", default="sh")

    args = parser.parse_args()

    return args

class Viewer(Gtk.Window):
    fields = ['name', 'email', 'username', 'source', 'id', 'uuid']
    fields_size = [300, 200, 150, 100, 100, 100]

    def __init__(self, sh_db=None):
        self.sh_db = sh_db
        Gtk.Window.__init__(self, title="SortingHat Viewer")
        w_width = 20
        for f in self.fields_size:
            w_width += f
        self.set_size_request(w_width, 450)

        # First, layout
        self.box = Gtk.VBox(spacing=6)
        self.add(self.box)

        # Add widgets to the layout
        self.button = Gtk.Button(label="Show identities")
        self.button.connect("clicked", self.on_show_identities)
        self.box.pack_start(self.button, False, False, 0)
        self.identities_liststore = Gtk.ListStore(str, str, str, str, str, str)
        self.treeview = Gtk.TreeView.new_with_model(self.identities_liststore)
        self.treeview.get_selection().connect("changed", self.on_tree_selection_changed)
        for i, column_title in enumerate(self.fields):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            column.set_max_width(self.fields_size[i])
            column.set_sort_column_id(i)
            self.treeview.append_column(column)
        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_vexpand(True)
        self.scrollable_treelist.add(self.treeview)
        self.box.pack_start(self.scrollable_treelist, True, True, 0)

    def on_tree_selection_changed(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter != None:
            text = ''
            for i, column_title in enumerate(self.fields):
                text += ','
                data = model[treeiter][i]
                if data:
                    text += model[treeiter][i]
            print("You selected", text[1:])

    def on_show_identities(self, widget):
        logging.debug("Getting identities")
        uids = api.unique_identities(self.sh_db)
        logging.debug("Showing identities")
        ndebug = 0
        for uid in uids:
            if ndebug > 10000:
                break
            ndebug += 1
            sh_id = []
            sh_id_dict = uid.to_dict()['identities'][0]
            for f in self.fields:
                sh_id.append(sh_id_dict[f])
            self.identities_liststore.append(list(sh_id))


if __name__ == '__main__':
    # CTRL-C support
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

    args = get_params()
    # args.db_sh must exists already
    db = Database(args.db_user, args.db_password, args.db_sh, args.db_host)

    win = Viewer(db)
    win.connect("delete-event", Gtk.main_quit)
    win.show_all()
    Gtk.main()
