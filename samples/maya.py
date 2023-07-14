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
    

def compare_models(model_1, model_2, extra_models=None):
    """
    Compares vertex values (and order) of the provided models.

    :param model_1: transform or shape node
    :type: str

    :param model_2: transform or shape node
    :type: str
    
    :param extra_models: additional model(s) to also compare
    :type: [str] or str
    
    :return: True if all provided models have the same vertex set.
    :type: bool
    """
    # collect models into a single list
    models = [model_1, model_2]
    if isinstance(extra_models, str):
        extra_models = [extra_models]
    if extra_models:
        models += extra_models
    
    # remove duplicate models
    models = set(models)
    
    # get vertex data for models
    verts = [get_verts_in_local_space(model) for model in models]
    
    # compare all models
    for i in range(1, len(models)):
        verts_1 = verts[i-1]
        verts_2 = verts[i]
        is_equal = len(verts_1) == len(verts_2) and verts_1 == verts_2
        
        # models were different
        # short-circuit and return false
        if not is_equal:
            return False
    
    return True
