from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint
from utils.database import get_relevant_drop_by_id, update_relevant_drop, delete_relevant_drop, get_tile_triggers, \
    get_tile_types, get_player_names
from utils.auth import admin_required

relevant_drop_routes = Blueprint("relevant_drop_management", __name__)

# Edit relevant drop
@relevant_drop_routes.route('/edit/<int:relevant_drops_pk>', methods=['GET', 'POST'])
@admin_required
def edit_relevant_drop(relevant_drops_pk):
    relevant_drop = get_relevant_drop_by_id(relevant_drops_pk)

    # Fetch necessary data for auto-filling form options
    tile_triggers = get_tile_triggers()  # Fetching the triggers for each tile
    tile_types = get_tile_types()        # Fetching the types of each tile
    player_names = get_player_names()

    if request.method == 'POST':
        new_tile_name = request.form.get('tile_name')
        new_drop_name = request.form.get('drop_name')
        new_player_name = request.form.get('player_name')

        update_relevant_drop(relevant_drops_pk, new_tile_name, new_drop_name, new_player_name)
        flash('Relevant drop updated successfully!', 'success')
        return redirect(request.url)

    # Pass relevant variables to the template
    return render_template('admin_templates/relevant_drop_templates/edit_relevant_drop.html',
                           relevant_drop=relevant_drop,
                           tile_triggers=tile_triggers,
                           tile_types=tile_types,
                           player_names=player_names)

# Delete relevant drop
@relevant_drop_routes.route('/delete/<int:relevant_drops_pk>', methods=['GET','POST'])
@admin_required
def delete_relevant_drop_route(relevant_drops_pk):
    delete_relevant_drop(relevant_drops_pk)
    flash('Relevant drop deleted successfully!', 'success')
    return redirect(request.url)
