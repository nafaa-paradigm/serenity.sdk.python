Serenity Project
================

This is a template project. You should replace serenity_project in `setup.cfg` with the project name in snake case, e.g. serenity_data_pipelines
and you should update all the TODO items in there. You will also want to add appropriate install_requires settings to match your project's
required libraries. Once `setup.cfg` cleaned up, rename `src/python/serenity_project` to match the project name as well; all Python code should
be added here with a root module matching the project name in snake case, e.g. `src/python/serenity_data_pipelines`.

You should also update serenity.project with the dot-delimited version of the project name in azure-pipelines.yml, e.g. 
serenity.data.pipelines. You will need to stand up the pipelines in Azure DevOps manually for now, but we might be able to script 
this all later if project setup is frequent enough.

Very important: you should also review `.devcontainer/docker-compose.yml` and make sure the appropriate mounts are in place for the 
upstream serenity projects. You will also need to replace the binding to `serenity.templates.python` with your project repo name
and you should change service name from serenity-project to your actual project name, dash-delimited. These settings will need to
be matched in `.devcontainer/devcontainer.json` -- specifically `workspaceFolder` and `service` will need to be updated.

To get a nice label in the devcontainer, you should also update the container name at the top of `.devcontainer/devcontainer.json`.

Once you have done all this, replace this README text with the project's documentation, and off you go with the new project.