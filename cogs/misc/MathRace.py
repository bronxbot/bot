import os
import json
import random
import math
import asyncio
from pathlib import Path
import nextcord
from nextcord.ext import commands
from cogs.logging.logger import CogLogger

logger = CogLogger('MathRace')
class MathRace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.EQUATION_FILE = Path("data/equations.json")
        self.EQUATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.logger = CogLogger(self.__class__.__name__)

    @commands.command(aliases=['mathduel', 'md', 'math'])
    async def mathrace(self, ctx, opponent: nextcord.Member = None, difficulty: int = 10):
        """Race to solve advanced math problems
        Difficulty levels: 1-30 (higher is harder)
        Example: .mathrace @User 15"""

        # Help command
        if (isinstance(difficulty, str) and difficulty.lower() == "help") or not opponent:
            examples = {
                "1 - Basic Addition": "`3 + 5`",
                "3 - Basic Multiplication": "`7 × 4`",
                "5 - Simple Algebra": "`2x + 3 = 11` (solve for x)",
                "8 - Linear Equations": "`3x - 7 = 2x + 5`",
                "12 - Quadratic Equations": "`x² - 5x + 6 = 0`",
                "15 - Basic Calculus": "`d/dx(3x²)`",
                "18 - Integration": "`∫(2x + 1) dx`",
                "22 - Advanced Calculus": "`lim(x→0) sin(x)/x`",
                "25 - Complex Numbers": "`(2+3i) × (1-2i)`",
                "28 - Matrix Operations": "`Det([[2,3],[1,4]])`",
                "30 - Differential Equations": "`dy/dx = 2y`"
            }

            embed = nextcord.Embed(
                title="Math Race Help",
                description="Challenge someone to solve math problems!\n"
                            "Choose a difficulty from **1 (easiest)** to **30 (hardest)**.\n\n"
                            "**Difficulty Examples:**",
                color=nextcord.Color.blue()
            )

            for level, example in examples.items():
                embed.add_field(name=f"Level {level}", value=example, inline=False)

            embed.set_footer(text="Usage: .mathrace @user [1-30]\nYou can also use `.mathrace help`")
            return await ctx.send(embed=embed)

        # Validate opponent
        if opponent == ctx.author:
            return await ctx.reply(embed=nextcord.Embed(
                description="You can't race against yourself!",
                color=nextcord.Color.red()
            ))
        if opponent.bot:
            return await ctx.reply(embed=nextcord.Embed(
                description="Bots can't race!",
                color=nextcord.Color.red()
            ))

        # Validate difficulty
        if not 1 <= difficulty <= 30:
            return await ctx.reply(embed=nextcord.Embed(
                description="Difficulty must be between 1 and 30!",
                color=nextcord.Color.red()
            ))

        # Challenge message
        embed = nextcord.Embed(
            description=f"🧮 **{opponent.mention}**, {ctx.author.mention} challenged you to a difficulty {difficulty} Math Race!\nReact with ✅ to accept within 30 seconds!",
            color=nextcord.Color.blue()
        )
        challenge_msg = await ctx.send(embed=embed)
        await challenge_msg.add_reaction("✅")

        def check(reaction, user):
            return (
                user == opponent and
                str(reaction.emoji) == "✅" and
                reaction.message.id == challenge_msg.id
            )

        try:
            await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
        except asyncio.TimeoutError:
            embed = nextcord.Embed(
                description=f"⌛ {opponent.mention} didn't accept the challenge in time!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        await challenge_msg.delete()

        # Generate problem
        game = MathGame()
        problem, answer = game.generate_problem(difficulty)

        # Calculate time limit (30 seconds for easy problems, up to 120 seconds for hardest)
        time_limit = min(30 + (difficulty * 3), 120)

        # Send problem
        embed = nextcord.Embed(
            title=f"🧮 Math Race (Difficulty {difficulty})",
            description=f"**Problem:**\n```{problem}```",
            color=nextcord.Color.blue()
        )
        embed.set_footer(text=f"You have {time_limit} seconds to answer!")
        await ctx.send(embed=embed)

        def check_answer(msg):
            if msg.author not in [ctx.author, opponent] or msg.channel != ctx.channel:
                return False
            
            try:
                user_answer = msg.content.strip().lower().replace(" ", "")
                
                # Handle numeric answers
                if isinstance(answer, (int, float)):
                    try:
                        user_num = float(user_answer)
                        return abs(user_num - float(answer)) < 0.01
                    except ValueError:
                        return False
                
                # Handle list of answers (multiple solutions)
                elif isinstance(answer, list):
                    try:
                        # Try numeric comparison first
                        user_num = float(user_answer)
                        return any(abs(user_num - float(str(ans).replace('i', '').replace('+', '').replace('-', ''))) < 0.01 
                                 for ans in answer if isinstance(ans, (int, float)))
                    except ValueError:
                        # Try string comparison for complex numbers and expressions
                        return any(user_answer == str(ans).lower().replace(" ", "") for ans in answer)
                
                # Handle string answers
                else:
                    correct_answer = str(answer).lower().replace(" ", "")
                    return user_answer == correct_answer
            
            except Exception as e:
                logger.error(f"Error checking answer: {e}")
                return False

        try:
            # Wait for a correct answer
            winner_msg = await self.bot.wait_for(
                "message",
                timeout=time_limit,
                check=check_answer
            )
            
            # Announce winner
            embed = nextcord.Embed(
                description=f"🏆 **{winner_msg.author.mention}** solved it first!\n**Answer:** `{answer}`",
                color=nextcord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except asyncio.TimeoutError:
            # Timeout if no one answered
            embed = nextcord.Embed(
                description=f"⌛ Time's up! No one solved the problem.\n**Answer:** `{answer}`",
                color=nextcord.Color.red()
            )
            await ctx.send(embed=embed)

class MathGame:
    def __init__(self):
        self.EQUATION_FILE = Path("data/equations.json")
        self.EQUATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.equations = self.load_equations()

    def load_equations(self):
        if not self.EQUATION_FILE.exists():
            with open(self.EQUATION_FILE, 'w') as f:
                json.dump({str(i): [] for i in range(1, 31)}, f, indent=4)
        try:
            with open(self.EQUATION_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {str(i): [] for i in range(1, 31)}

    def save_equation(self, diff, problem, answer):
        try:
            entry = {"problem": problem, "answer": answer}
            self.equations.setdefault(str(diff), []).append(entry)
            with open(self.EQUATION_FILE, 'w') as f:
                json.dump(self.equations, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving equation: {e}")

    def generate_problem(self, diff):
        # Check if a stored problem exists
        existing = self.equations.get(str(diff), [])
        if existing and random.random() < 0.3:  # 30% chance to use stored problem
            chosen = random.choice(existing)
            return chosen["problem"], chosen["answer"]

        # Generate new problem based on difficulty
        problem, answer = self._generate_by_difficulty(diff)
        
        # Save the new problem
        self.save_equation(diff, problem, answer)
        return problem, answer

    def _generate_by_difficulty(self, diff):
        """Generate problems with smooth difficulty progression from 1-30"""
        
        # Levels 1-4: Basic arithmetic
        if diff <= 4:
            if diff == 1:
                a, b = random.randint(1, 5), random.randint(1, 5)
                problem = f"{a} + {b}"
                answer = a + b
            elif diff == 2:
                a, b = random.randint(1, 10), random.randint(1, 10)
                op = random.choice(['+', '-'])
                problem = f"{a} {op} {b}"
                answer = eval(f"{a}{op}{b}")
            elif diff == 3:
                a, b = random.randint(2, 9), random.randint(2, 9)
                problem = f"{a} × {b}"
                answer = a * b
            else:  # diff == 4
                a, b = random.randint(2, 12), random.randint(2, 6)
                problem = f"{a * b} ÷ {b}"
                answer = a
        
        # Levels 5-8: Simple algebra
        elif diff <= 8:
            if diff <= 6:
                a = random.randint(2, 5)
                b = random.randint(1, 15)
                c = random.randint(1, 20)
                problem = f"{a}x + {b} = {c}"
                answer = round((c - b) / a, 2)
            else:
                a = random.randint(1, 5)
                b = random.randint(1, 10)
                c = random.randint(1, 15)
                d = random.randint(1, 10)
                problem = f"{a}x + {b} = {c}x + {d}"
                answer = round((d - b) / (a - c), 2) if a != c else "no solution"
        
        # Levels 9-12: Advanced algebra and quadratics
        elif diff <= 12:
            if diff <= 10:
                a = random.randint(1, 3)
                b = random.randint(-8, 8)
                c = random.randint(-10, 10)
                problem = f"{a}x² + {b}x + {c} = 0"
                discriminant = b**2 - 4*a*c
                if discriminant >= 0:
                    root1 = round((-b + math.sqrt(discriminant)) / (2 * a), 2)
                    root2 = round((-b - math.sqrt(discriminant)) / (2 * a), 2)
                    answer = [root1, root2] if root1 != root2 else [root1]
                else:
                    real = round(-b / (2 * a), 2)
                    imag = round(math.sqrt(-discriminant) / (2 * a), 2)
                    answer = [f"{real}+{imag}i", f"{real}-{imag}i"]
            else:
                # System of equations
                a, b = random.randint(1, 3), random.randint(1, 3)
                c, d = random.randint(1, 3), random.randint(1, 3)
                e, f = random.randint(1, 10), random.randint(1, 10)
                problem = f"{a}x + {b}y = {e}\n{c}x + {d}y = {f}"
                det = a*d - b*c
                if det != 0:
                    x = round((e*d - b*f) / det, 2)
                    y = round((a*f - e*c) / det, 2)
                    answer = f"x={x}, y={y}"
                else:
                    answer = "no unique solution"
        
        # Levels 13-16: Basic calculus
        elif diff <= 16:
            if diff <= 14:
                coeff = random.randint(1, 5)
                power = random.randint(2, 4)
                problem = f"d/dx({coeff}x^{power})"
                answer = f"{coeff * power}x^{power - 1}" if power - 1 > 1 else f"{coeff * power}x" if power - 1 == 1 else str(coeff * power)
            else:
                coeff = random.randint(1, 5)
                power = random.randint(1, 3)
                problem = f"∫({coeff}x^{power}) dx"
                new_power = power + 1
                new_coeff = coeff / new_power
                if new_coeff == int(new_coeff):
                    new_coeff = int(new_coeff)
                answer = f"{new_coeff}x^{new_power} + C" if new_power > 1 else f"{new_coeff}x + C"
        
        # Levels 17-20: Intermediate calculus
        elif diff <= 20:
            choices = ['product_rule', 'chain_rule', 'definite_integral', 'limit']
            choice = random.choice(choices)
            
            if choice == 'product_rule':
                a, b = random.randint(1, 3), random.randint(1, 3)
                problem = f"d/dx(x^{a} × x^{b})"
                power = a + b
                answer = f"{power}x^{power-1}" if power > 1 else str(power)
            elif choice == 'chain_rule':
                a, b = random.randint(2, 4), random.randint(1, 3)
                problem = f"d/dx(({a}x + {b})^2)"
                answer = f"{2*a}({a}x + {b})" if a != 1 else f"2({a}x + {b})"
            elif choice == 'definite_integral':
                coeff = random.randint(1, 4)
                a, b = random.randint(0, 2), random.randint(3, 5)
                problem = f"∫({coeff}x) dx from {a} to {b}"
                answer = coeff * (b**2 - a**2) / 2
            else:
                problem = "lim(x→0) sin(x)/x"
                answer = 1
        
        # Levels 21-24: Advanced calculus
        elif diff <= 24:
            choices = ['partial_derivative', 'double_integral', 'series', 'complex_limit']
            choice = random.choice(choices)
            
            if choice == 'partial_derivative':
                a, b = random.randint(1, 3), random.randint(1, 3)
                problem = f"∂/∂x(x^{a} × y^{b})"
                answer = f"{a}x^{a-1} × y^{b}" if a > 1 else f"y^{b}"
            elif choice == 'double_integral':
                problem = "∫∫(xy) dx dy from x=0 to 1, y=0 to 1"
                answer = 0.25
            elif choice == 'series':
                problem = "Sum of geometric series: 1 + 1/2 + 1/4 + 1/8 + ..."
                answer = 2
            else:
                problem = "lim(x→∞) (1 + 1/x)^x"
                answer = "e"
        
        # Levels 25-27: Complex numbers and advanced algebra
        elif diff <= 27:
            if diff <= 26:
                a, b = random.randint(1, 4), random.randint(1, 4)
                c, d = random.randint(1, 4), random.randint(1, 4)
                problem = f"({a} + {b}i) × ({c} + {d}i)"
                real = a * c - b * d
                imag = a * d + b * c
                answer = f"{real} + {imag}i" if imag >= 0 else f"{real} - {abs(imag)}i"
            else:
                a, b = random.randint(1, 4), random.randint(1, 4)
                problem = f"|{a} + {b}i|"
                answer = round(math.sqrt(a**2 + b**2), 2)
        
        # Levels 28-30: Matrix operations and differential equations
        else:
            if diff <= 29:
                a, b = random.randint(1, 4), random.randint(1, 4)
                c, d = random.randint(1, 4), random.randint(1, 4)
                problem = f"Det([[{a}, {b}], [{c}, {d}]])"
                answer = a * d - b * c
            else:
                coeff = random.randint(2, 4)
                problem = f"Solve: dy/dx = {coeff}y"
                answer = f"y = Ce^({coeff}x)"
        
        return problem, answer

async def setup(bot):
    try:
        bot.add_cog(MathRace(bot))
    except Exception as e:
        raise e