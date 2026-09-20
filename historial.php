<html>
    <head>
        <title>Historial</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>        
    </head>
    </head>
        <title>Restaurante "La nonna"</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
    
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    
        <link rel="stylesheet" href="style.css">
    </head>
    <body class="d-flex flex-column min-vh-100">
        <!--Navbar -->
        <nav class="navbar navbar-expand-sm bg-dark navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="index.php">Logo</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                    <span class="navbar-toggler-icon"></span>
                </button> 
                <div class="collapse navbar-collapse" id="collapsibleNavbar">
                    <ul class="navbar-nav">            
                        <li class="nav-item">
                            <a class="nav-link" href="carta.php">Carta</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="historial.php">Historial</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="carrito.php">Carrito</a>
                        </li>                                               
                    </ul>
                </div>  
                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#myModal">Acceder</button>                             
            </div>
        </nav>
        <!--Modal-->
        <!--Modal Principal-->
        <div class="modal fade" id="myModal">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Autenticacion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <div class="row">
                            <!-- Izquierda: Usuario / Crear cuenta -->
                            <div class="col-sm-6 border-end">
                                <h5>Usuario</h5>
                                <form action="registro.php">
                                    <div class="mb-3 mt-3">
                                        <label for="emailUser" class="form-label">Email:</label>
                                        <input type="email" class="form-control" id="emailUser" placeholder="Enter email" name="email">
                                    </div>
                                    <button type="submit" class="btn btn-primary mb-3">Crear cuenta</button>
                                </form>
                                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#loginModal">Iniciar sesion</button>
                            </div>

                            <!-- Derecha: Trabajadores -->
                            <div class="col-sm-6">
                                <h5>Trabajadores</h5>
                                <form action="trabajador.php">
                                    <div class="mb-3 mt-3">
                                        <label for="emailTrab" class="form-label">Email:</label>
                                        <input type="email" class="form-control" id="emailTrab" placeholder="Enter email" name="email">
                                    </div>
                                    <div class="mb-3">
                                        <label for="pwdTrab" class="form-label">Password:</label>
                                        <input type="password" class="form-control" id="pwdTrab" placeholder="Enter password" name="pswd">
                                    </div>
                                    <button type="submit" class="btn btn-primary">Login</button>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>

        <!--Modal Inicio Sesion Usuario-->
        <div class="modal fade" id="loginModal">
            <div class="modal-dialog">
                <div class="modal-content">
                    <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Inicio de sesion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <form action="empresa.php">
                            <div class="mb-3 mt-3">
                                <label for="email" class="form-label">Email:</label>
                                <input type="email" class="form-control" id="email" placeholder="Enter email" name="email">
                            </div>
                            <div class="mb-3">
                                <label for="pwd" class="form-label">Password:</label>
                                <input type="password" class="form-control" id="pwd" placeholder="Enter password" name="pswd">
                            </div>
                            <div class="form-check mb-3">
                                <label class="form-check-label">
                                    <input class="form-check-input" type="checkbox" name="remember"> Remember me
                                </label>
                            </div>
                            <button type="submit" class="btn btn-primary">Login</button>
                        </form>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-toggle="modal" data-bs-target="#myModal">Volver</button>
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="container-fluid bg-dark mt-auto py-3 text-white text-center">
            <div class="row">
                <div class="col-4"></div>
                <div class="col-4" style="color:gray"><strong>MiEmpresa@2026</strong></div>
                <div class="col-4"></div>
            </div>
        </div>

        <script src="js/app.js"></script>
    </body>
</html>