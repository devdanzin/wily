Bulk Annotate Command
=====================

The bulk_annotate command will bulk generate annotated Python source as HTML for all known files in a repository.

Examples
--------

To bulk annotate files, simply call ``wily bulk_annotate``

.. code-block:: none

  $ wily bulk_annotate

By default, ``wily bulk_annotate`` will create files in the ``reports`` subdirectory.
To save the output to another directory, provide the ``-o`` flag and the name of the output directory.

.. code-block:: none

   $ wily bulk_annotate -o annotated_source/

Command Line Usage
------------------

.. click:: wily.__main__:bulk_annotate
   :prog: wily
   :show-nested:
