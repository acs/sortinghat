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
    ALL_FIELD = 'all'
    multiple_selection = True
    fields = ['name', 'email', 'username', 'source', 'id', 'uuid']
    fields_size = [300, 200, 150, 100, 100, 100]

    def __init__(self, sh_db=None):
        self.sh_db = sh_db

        self.identities_liststore = None  # Identities data store
        self.sources_liststore = None  # SH sources data store

        self.__layout()

    def __layout(self):
        Gtk.Window.__init__(self, title="SortingHat Viewer")
        w_width = 20
        for f in self.fields_size:
            w_width += f
        self.set_size_request(w_width, 450)

        # First, layout
        self.box = Gtk.VBox(spacing=6)
        self.add(self.box)

        # Filter HBox
        self.filter_box = Gtk.HBox(spacing=6)
        self.box.pack_start(self.filter_box, False, False, 0)

        # Sample Button for loading the identities
        self.button = Gtk.Button(label="Load identities")
        self.button.connect("clicked", self.on_show_identities)
        self.filter_box.pack_start(self.button, False, False, 0)

        # Combo for filterting using data sources
        self.sources_liststore = Gtk.ListStore(str)
        self.sources_liststore.append([None])
        sources_combo = Gtk.ComboBox.new_with_model(self.sources_liststore)
        renderer_text = Gtk.CellRendererText()
        sources_combo.pack_start(renderer_text, True)
        sources_combo.add_attribute(renderer_text, "text", 0)
        sources_combo.connect("changed", self.on_name_combo_changed)
        self.filter_box.pack_start(sources_combo, False, False, 0)
        self.current_filter_source = None

        # Combo + entry box for free text searching
        self.search_text = Gtk.Entry()
        self.search_text.set_text("Search")
        self.search_text.connect("activate", self.on_search_text_changed)
        self.filter_box.pack_start(self.search_text, True, True, 0)
        self.current_filter_search = None

        self.sources_liststore_all = Gtk.ListStore(str)
        self.sources_liststore_all.append([self.ALL_FIELD])
        for f in self.fields:
            self.sources_liststore_all.append([f])
        sources_search = Gtk.ComboBox.new_with_model(self.sources_liststore_all)
        renderer_text = Gtk.CellRendererText()
        sources_search.pack_start(renderer_text, True)
        sources_search.add_attribute(renderer_text, "text", 0)
        sources_search.connect("changed", self.on_sources_search_changed)
        self.filter_box.pack_start(sources_search, False, False, 0)
        self.current_filter_source_search = None

        # Identities viewer
        self.identities_liststore = Gtk.ListStore(str, str, str, str, str, str)
        self.source_filter = self.identities_liststore.filter_new()
        self.source_filter.set_visible_func(self.source_filter_func)
        self.search_filter = self.source_filter.filter_new()
        self.search_filter.set_visible_func(self.source_filter_search_func)
        self.treeview = Gtk.TreeView.new_with_model(self.search_filter)
        if self.multiple_selection:
            self.treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
            self.treeview.get_selection().connect("changed", self.on_tree_selection_multiple_changed)
        else:
            self.treeview.get_selection().connect("changed", self.on_tree_selection_single_changed)
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

        self.sources = []  # list with the data sources available

        # Actions button bar
        self.action_box = Gtk.HBox(spacing=6)
        self.box.pack_start(self.action_box, False, False, 0)

        # Sample Button for merging identities
        self.button_merge = Gtk.Button(label="Merge identities")
        self.button_merge.connect("clicked", self.on_merge_identities)
        self.filter_box.pack_start(self.button_merge, False, False, 0)

    def on_search_text_changed(self, entry):
        self.current_filter_search = entry.get_text()
        logging.debug("Activate received from entry text %s", self.current_filter_search)
        self.search_filter.refilter()

    def on_sources_search_changed(self, combo):
        pass

    def on_merge_identities(self, combo):
        logging.debug("Merging identities")
        selection = self.treeview.get_selection()
        model, pathlist = selection.get_selected_rows()
        ids = []
        if model != None:
            logging.debug("ids to merge ...")
            for path in pathlist:
                # id is the 5th field
                ids.append(model[path][5])
                logging.debug ("id:", model[path][5])
            logging.debug("Merging identities")
            to_uuid = ids[0]  # merge all ids with the first one
            for uid in ids:
                api.merge_unique_identities(self.sh_db, uid, to_uuid)
            logging.debug("Merging done")

    def source_filter_func(self, model, iter, data):
        """Tests if the source in the row is the one in the filter"""
        if self.current_filter_source is None or self.current_filter_source == "None":
            return True
        else:
            return model[iter][3] == self.current_filter_source

    def source_filter_search_func(self, model, iter, data):
        """Tests if the search text in the row is the one in the filter"""
        found = False
        if self.current_filter_search is None or self.current_filter_search == "None":
            return True
        else:
            found = False
            # Try to find the text in all fields
            for col in model[iter]:
                if not col:
                    continue
                if self.current_filter_search in col:
                    found = True
                    break
        return found

    def on_name_combo_changed(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter != None:
            model = combo.get_model()
            source = model[tree_iter][0]
            logging.debug("Selected: source=%s" % source)
            self.current_filter_source = source
            # self.current_filter_source = combo.get_label()
            self.source_filter.refilter()

    def on_tree_selection_multiple_changed(self, selection):
        model, pathlist = selection.get_selected_rows()
        if model != None:
            text = ''
            for path in pathlist:
                for i, column_title in enumerate(self.fields):
                    text += ','
                    data = model[path][i]
                    if data:
                        text += model[path][i]
                text += '\n'
        # print(text)


    def on_tree_selection_single_changed(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter != None:
            text = ''
            for i, column_title in enumerate(self.fields):
                text += ','
                data = model[treeiter][i]
                if data:
                    text += model[treeiter][i]
        print(text)

    def on_show_identities(self, widget):
        logging.debug("Getting identities")
        uids = api.unique_identities(self.sh_db)
        logging.debug("Showing identities")
        ntotal = 0
        for uid in uids:
            ntotal += 1
            # if ntotal > 1000:
            #     break
            sh_id = []
            sh_id_dict = uid.to_dict()['identities'][0]
            for f in self.fields:
                sh_id.append(sh_id_dict[f])
                if f == 'source':
                    if sh_id_dict[f] not in [r[0] for r in self.sources_liststore]:
                        self.sources_liststore.append([sh_id_dict[f]])
            self.identities_liststore.append(list(sh_id))
        logging.debug("Total identities: %i", ntotal)


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
