#----------------------------------------------------------------------------------------#
#----------------------------------------------------------------------------- IMPORTS --#

# Third Party
import maya.cmds as cmds

#----------------------------------------------------------------------------------------#
#--------------------------------------------------------------------------- FUNCTIONS --#

def get_verts_in_local_space(model):
    """
    Gets a list of vertex positions (in local space) for a model.

    :param model: transform or shape node
    :type: str

    :returns: list of vertex positions
    :type: list
    """
    verts = []
    verts_amount = cmds.getAttr(f"{model}.vrts", multiIndices=True)

    for i in verts_amount:
        position = cmds.xform(f"{model}.pnts[{i}]", query=True, translation=True)
        verts.append(position)

    return verts
    

def compare_models(model_1, model_2):
    """
    Compares vertex values (and order) of the provided models.

    :param model_1: transform or shape node
    :type: str

    :param model_2: transform or shape node
    :type: str
    
    :return: True if both shape nodes contain the same vertex set
    :type: bool
    """
    verts_1 = get_verts_in_local_space(model_1)
    verts_2 = get_verts_in_local_space(model_2)

    return len(verts_1) == len(verts_2) and verts_1 == verts_2
