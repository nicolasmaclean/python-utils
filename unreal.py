# ----------------------------------------------------------------------------------------#
# ----------------------------------------------------------------------------- IMPORTS --#

# Built-In
import os

# Third Party
import unreal

# Internal
from unreal_tools.unreal_guis.unreal_guis import notify_user
from unreal_tools.unreal_lighting_utils import (Renderer, build_render_preset_from_xml,
                                                RENDER_PRESET)
from unreal_tools.unreal_utils import (get_unreal_pipe_context, get_main_level_path,
                                       get_main_sequence_path)

# External
from gen_utils.pipe_enums import RESULT_TYPES, OS

# ----------------------------------------------------------------------------------------#
# --------------------------------------------------------------------------- FUNCTIONS --#


def render_main_level_and_sequence(preset):
    """
    Renders the main level and sequence with the provided preset.

    :param preset: Render settings
    :type: str or unreal.MoviePipelineMasterConfig

    :return: The renderer that will be used
    :type: Renderer
    """
    main_level_path = get_main_level_path()
    if not unreal.EditorAssetLibrary.does_asset_exist(main_level_path):
        notify_user('Render Shot', 'Unable to find the main level asset.',
                    RESULT_TYPES.FAILURE)
        return None

    main_sequence_path = get_main_sequence_path()
    if not unreal.EditorAssetLibrary.does_asset_exist(main_sequence_path):
        notify_user('Render Shot', 'Unable to find the main level sequence asset.',
                    RESULT_TYPES.FAILURE)
        return None

    renderer = Renderer.render_shot(main_level_path, main_sequence_path, preset)

    return renderer


def render_main_level_with_global_preset(preset_file_name=RENDER_PRESET.LOW):
    """
    Renders the level with a preset from the project configs.

    :param preset_file_name: file name of a global render preset
    :type: unreal_lighting_utils.RENDER_PRESET

    :return: Success of the operation
    :type: bool
    """
    # build path to preset
    context = get_unreal_pipe_context()
    render_settings_path = context.eval_path('pr_project_ren_set_dir', drive=OS.drive)
    preset_path = os.path.join(render_settings_path, f"{preset_file_name}.xml")

    # read preset
    preset = build_render_preset_from_xml(preset_path)
    if not preset:
        notify_user('Render Shot', f'Unable to find the {preset_file_name} render preset.',
                    RESULT_TYPES.WARNING)
        return None

    # render shot
    render_main_level_and_sequence(preset)
    return True

def render_low():
    """
    Wrapper of render_main_level_with_global_preset with the low preset.

    :return: Success of the operation
    :type: bool
    """
    return render_main_level_with_global_preset(RENDER_PRESET.LOW)

def render_high():
    """
    Wrapper of render_main_level_with_global_preset with the high preset.

    :return: Success of the operation
    :type: bool
    """
    return render_main_level_with_global_preset(RENDER_PRESET.HIGH)

def render_final():
    """
    Wrapper of render_main_level_with_global_preset with the final preset.

    :return: Success of the operation
    :type: bool
    """
    return render_main_level_with_global_preset(RENDER_PRESET.FINAL)
